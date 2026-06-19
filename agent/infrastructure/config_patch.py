"""运行时配置补丁（保留原有 base64 混淆逻辑，避免扩散到通用工具模块）。"""

from base64 import b64decode

from utils import jD, jL, root
from utils.logger import logger


def _bdc(s: str) -> str:
    """Base64 decode helper，与历史实现保持一致。"""
    return b64decode(s).decode("utf-8")


def validate_config(context: object) -> None:
    """验证并补丁安装目录下的 interface.json 元信息。"""
    if len(list(root.glob("*.exe"))) == 0:
        return
    try:
        fp = next(p for p in root.glob("*.json") if p.name.startswith("in"))
    except StopIteration:
        return

    logger.info(f"验证配置文件: {fp}")
    config = jL(fp.open(encoding="utf-8"))
    config.update(
        {
            _bdc("bmFtZQ=="): _bdc("TWFhQXV0b05hcnV0bw=="),
            _bdc("Z2l0aHVi"): _bdc(
                "aHR0cHM6Ly9naXRodWIuY29tL2R1b3J1YS9uYXJ1dG9tb2JpbGU="
            ),
            _bdc("bWlycm9yY2h5YW5fcmlk"): _bdc("TWFhQXV0b05hcnV0bw=="),
        }
    )
    jD(config, fp.open("w", encoding="utf-8"), ensure_ascii=False, indent=4)


def validate_mfa(context: object) -> None:
    """验证并补丁 MFA 配置。"""
    fps = [p for p in (root / "config").glob("*.json") if p.name.startswith("c")]
    if len(fps) != 0:
        fp = fps[0]
    else:
        return
    mfa = jL(fp.open(encoding="utf-8"))
    if mfa.get(_bdc("RG93bmxvYWRDREs="), "") == "":
        mfa.update(
            {
                _bdc("RG93bmxvYWRTb3VyY2VJbmRleA=="): 0,
            }
        )

    mfa.update(
        {
            _bdc("RW5hYmxlQXV0b1VwZGF0ZVJlc291cmNl"): True,
            _bdc("RW5hYmxlQXV0b1VwZGF0ZU1GQQ=="): True,
        }
    )
