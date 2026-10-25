"""Register Veyr's project-specific import workflow in Epic's native MCP registry."""
from pathlib import Path
import sys
import unreal

_root = Path(unreal.Paths.project_dir()).resolve().parents[1]
_tools = _root / 'tools/unreal'
if str(_tools) not in sys.path:
    sys.path.insert(0, str(_tools))
from veyr_integration_toolset import VeyrIntegrationTools
unreal.ToolsetRegistry.register_toolset_class(VeyrIntegrationTools)
import test_veyr_integration
test_veyr_integration._test_runner = unreal.PythonTestRunner.create(
    'Veyr.Integration', unreal.PythonTestRunnerSearchOptions(root_module=test_veyr_integration.__name__))
