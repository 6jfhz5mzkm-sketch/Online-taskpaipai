"""ORM 模型包导出契约回归(M4)。

背景:app/db/models/__init__.py 的 __all__ 与上面的 import 列表不一致(7 个模型模块未列入),
形成两份互相漂移的清单。修复后二者一一对应,本用例守护该一致性。
"""

import types

import app.db.models as models_pkg


def test_all_matches_imported_model_modules():
    declared = set(models_pkg.__all__)
    imported_modules = {
        name for name, obj in vars(models_pkg).items()
        if isinstance(obj, types.ModuleType) and getattr(obj, "__name__", "").startswith("app.db.models.")
    }
    assert declared == imported_modules | {"Base"}, declared.symmetric_difference(imported_modules | {"Base"})
