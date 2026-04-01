"""
提示模板加载器 - DEV-002 提示管理系统

功能：
- YAML模板加载与解析
- 模板继承与合并
- 条件包含处理
- 变量替换
- 缓存机制
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


class TemplateNotFoundError(Exception):
    """模板未找到异常"""
    pass


class TemplateLoadError(Exception):
    """模板加载错误"""
    pass


class TemplateValidationError(Exception):
    """模板验证错误"""
    pass


@dataclass
class TemplateInfo:
    """模板元信息"""
    name: str
    path: str
    version: str = "1.0"
    description: str = ""
    variables: list[str] = field(default_factory=list)
    extends: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    ttl: int

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class TemplateCache:
    """模板缓存 (LRU)"""

    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []

    def get(self, key: str) -> Any | None:
        """获取缓存"""
        entry = self._cache.get(key)
        if entry is None:
            return None

        if entry.is_expired():
            self._remove(key)
            return None

        # 更新访问顺序 (LRU)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存"""
        # 如果已满，删除最旧的
        if len(self._cache) >= self.max_size and key not in self._cache:
            if self._access_order:
                oldest = self._access_order.pop(0)
                self._remove(oldest)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl=ttl or self.default_ttl
        )
        self._cache[key] = entry

        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def invalidate(self, key: str) -> None:
        """使缓存失效"""
        self._remove(key)

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()

    def _remove(self, key: str) -> None:
        """移除缓存项"""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            self._access_order.remove(key)

    @property
    def stats(self) -> dict[str, Any]:
        """缓存统计"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "keys": list(self._cache.keys())
        }


class TemplateLoader:
    """提示模板加载器
    
    主要功能：
    1. 从YAML文件加载模板
    2. 处理模板继承 (extends)
    3. 处理条件包含 (includes)
    4. 变量插值替换
    5. 模板缓存
    """

    def __init__(
        self,
        template_dir: Path | str,
        cache_enabled: bool = True,
        cache_max_size: int = 100,
        cache_ttl: int = 3600
    ):
        self.template_dir = Path(template_dir)
        self.cache_enabled = cache_enabled
        self._cache = TemplateCache(
            max_size=cache_max_size,
            default_ttl=cache_ttl
        )
        self._registry: dict[str, TemplateInfo] = {}

        # 确保目录存在
        if not self.template_dir.exists():
            logger.warning(
                "template_dir_not_found",
                path=str(self.template_dir)
            )

    def load(
        self,
        template_name: str,
        version: str | None = None,
        variables: dict[str, Any] | None = None,
        use_cache: bool = True
    ) -> dict[str, Any]:
        """
        加载提示模板
        
        Args:
            template_name: 模板名称 (如 "agents/main", "system/base")
            version: 版本号，默认最新
            variables: 用于插值的变量字典
            use_cache: 是否使用缓存
            
        Returns:
            模板数据字典
        """
        cache_key = f"{template_name}:{version or 'latest'}"

        # 检查缓存
        if use_cache and self.cache_enabled:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("template_cache_hit", key=cache_key)
                return self._interpolate(cached, variables or {})

        # 加载模板
        template_path = self._resolve_path(template_name)
        if not template_path.exists():
            raise TemplateNotFoundError(
                f"Template not found: {template_name} (path: {template_path})"
            )

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise TemplateLoadError(
                f"Failed to parse template {template_name}: {e}"
            )

        # 验证模板
        self._validate_template(template_data, template_name)

        # 处理模板继承
        if "extends" in template_data:
            parent_name = template_data["extends"]
            parent = self.load(parent_name, version, variables, use_cache)
            template_data = self._merge(parent, template_data)

        # 处理条件包含
        if "includes" in template_data:
            template_data = self._process_includes(
                template_data,
                variables or {},
                version,
                use_cache
            )

        # 缓存结果
        if use_cache and self.cache_enabled:
            self._cache.set(cache_key, template_data)

        logger.info(
            "template_loaded",
            name=template_name,
            version=version,
            has_extends="extends" in template_data
        )

        # 变量插值
        return self._interpolate(template_data, variables or {})

    def load_raw(self, template_name: str) -> dict[str, Any]:
        """
        加载原始模板数据（不处理继承和插值）
        """
        template_path = self._resolve_path(template_name)
        if not template_path.exists():
            raise TemplateNotFoundError(f"Template not found: {template_name}")

        with open(template_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _resolve_path(self, template_name: str) -> Path:
        """解析模板文件路径"""
        parts = template_name.split("/")
        if len(parts) == 1:
            # 单层名称，尝试在所有目录中查找
            for subdir in ["system", "agents", "tools", "memory"]:
                path = self.template_dir / subdir / f"{template_name}.yaml"
                if path.exists():
                    return path
            return self.template_dir / f"{template_name}.yaml"
        else:
            # 多层名称，直接拼接
            return self.template_dir / f"{parts[0]}" / f"{parts[-1]}.yaml"

    def _merge(self, parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
        """合并父子模板（深度合并）"""
        result = parent.copy()

        for key, value in child.items():
            if key == "extends":
                continue

            if (
                isinstance(value, dict) and
                key in result and
                isinstance(result[key], dict)
            ):
                # 深度合并字典
                result[key] = self._merge(result[key], value)
            elif isinstance(value, list) and key in result and isinstance(result[key], list):
                # 列表合并（去重）
                result[key] = list(set(result[key] + value))
            else:
                # 直接覆盖
                result[key] = value

        return result

    def _process_includes(
        self,
        template_data: dict[str, Any],
        variables: dict[str, Any],
        version: str | None = None,
        use_cache: bool = True
    ) -> dict[str, Any]:
        """处理条件包含"""
        result = template_data.copy()
        includes = result.pop("includes", [])

        for include in includes:
            condition = include.get("when", {})
            if self._check_condition(condition, variables):
                included_name = include["template"]
                try:
                    included = self.load(
                        included_name,
                        version,
                        variables,
                        use_cache
                    )
                    result = self._merge(result, included)
                    logger.debug(
                        "include_processed",
                        template=included_name,
                        condition=condition
                    )
                except TemplateNotFoundError:
                    logger.warning(
                        "include_not_found",
                        template=included_name
                    )

        return result

    def _check_condition(
        self,
        condition: dict[str, Any],
        variables: dict[str, Any]
    ) -> bool:
        """检查条件是否满足"""
        if not condition:
            return True

        for key, expected in condition.items():
            actual = variables.get(key)
            if actual is None:
                return False
            if isinstance(expected, bool):
                if not actual:
                    return False
            elif actual != expected:
                return False

        return True

    def _interpolate(
        self,
        template_data: dict[str, Any],
        variables: dict[str, Any]
    ) -> dict[str, Any]:
        """变量插值替换"""
        result = {}

        for key, value in template_data.items():
            if isinstance(value, str):
                result[key] = self._interpolate_string(value, variables)
            elif isinstance(value, dict):
                result[key] = self._interpolate(value, variables)
            elif isinstance(value, list):
                result[key] = [
                    self._interpolate_string(item, variables)
                    if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    def _interpolate_string(self, text: str, variables: dict[str, Any]) -> str:
        """插值字符串中的变量"""
        import re

        # 替换 {{variable}} 格式
        def replace_var(match):
            var_name = match.group(1)
            value = variables.get(var_name, match.group(0))
            return str(value)

        text = re.sub(r'\{\{(\w+)\}\}', replace_var, text)

        # 替换 ${variable} 格式
        text = re.sub(r'\$\{(\w+)\}', replace_var, text)

        return text

    def _validate_template(
        self,
        template_data: dict[str, Any],
        template_name: str
    ) -> None:
        """验证模板结构"""
        if not isinstance(template_data, dict):
            raise TemplateValidationError(
                f"Template {template_name} must be a dictionary"
            )

        # 必需字段检查
        if "content" not in template_data:
            logger.warning(
                "template_missing_content",
                template=template_name
            )

    def register(self, name: str, info: TemplateInfo) -> None:
        """注册模板元信息"""
        self._registry[name] = info
        logger.debug("template_registered", name=name)

    def unregister(self, name: str) -> None:
        """注销模板"""
        if name in self._registry:
            del self._registry[name]
        self._cache.invalidate(name)

    def list_templates(self) -> list[str]:
        """列出所有已注册模板"""
        return list(self._registry.keys())

    def scan_templates(self) -> list[TemplateInfo]:
        """扫描模板目录，返回所有模板信息"""
        templates = []

        for yaml_file in self.template_dir.rglob("*.yaml"):
            try:
                rel_path = yaml_file.relative_to(self.template_dir)
                template_name = str(rel_path.with_suffix("")).replace("/", "/")

                template_data = yaml.safe_load(yaml_file.read_text())
                info = TemplateInfo(
                    name=template_data.get("name", template_name),
                    path=str(yaml_file),
                    version=template_data.get("version", "1.0"),
                    description=template_data.get("description", ""),
                    variables=template_data.get("variables", []),
                    extends=template_data.get("extends"),
                    metadata=template_data.get("metadata", {})
                )
                templates.append(info)
            except Exception as e:
                logger.warning(
                    "template_scan_error",
                    path=str(yaml_file),
                    error=str(e)
                )

        return templates

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("template_cache_cleared")

    @property
    def cache_stats(self) -> dict[str, Any]:
        """缓存统计"""
        return self._cache.stats


# 模块级单例
_loader_instance: TemplateLoader | None = None


def get_loader(
    template_dir: Path | str | None = None,
    **kwargs: Any
) -> TemplateLoader:
    """获取模板加载器实例（单例）"""
    global _loader_instance

    if _loader_instance is None:
        if template_dir is None:
            # 默认模板目录
            template_dir = Path(__file__).parent / "templates"
        _loader_instance = TemplateLoader(template_dir, **kwargs)

    return _loader_instance


def reset_loader() -> None:
    """重置加载器实例（测试用）"""
    global _loader_instance
    _loader_instance = None
