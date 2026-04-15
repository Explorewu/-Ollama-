# -*- coding: utf-8 -*-
"""
统一模型下载器
整合 download_models.py、download_with_mirror.py、re_download.py 的功能
支持多镜像源切换、断点续传、进度显示、错误重试
"""
import os
import sys
import time
import logging
import shutil
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MirrorSource(Enum):
    """镜像源枚举"""
    WISEMODEL = "wisemodel"
    HF_MIRROR = "hf_mirror"
    MODELSCOPE = "modelscope"
    HUGGINGFACE = "huggingface"


@dataclass
class MirrorConfig:
    """镜像源配置"""
    name: str
    url: str
    speed: str = "未知"
    status: str = "未知"
    priority: int = 0


MIRROR_CONFIGS: Dict[MirrorSource, MirrorConfig] = {
    MirrorSource.WISEMODEL: MirrorConfig(
        name="Wisemodel (智谱AI)",
        url="https://wisemodel.cn",
        speed="最快",
        status="稳定",
        priority=1
    ),
    MirrorSource.HF_MIRROR: MirrorConfig(
        name="HF-Mirror",
        url="https://hf-mirror.com",
        speed="快",
        status="稳定",
        priority=2
    ),
    MirrorSource.MODELSCOPE: MirrorConfig(
        name="ModelScope (阿里达摩院)",
        url="https://modelscope.cn",
        speed="快",
        status="稳定",
        priority=3
    ),
    MirrorSource.HUGGINGFACE: MirrorConfig(
        name="HuggingFace (官方)",
        url="https://huggingface.co",
        speed="慢",
        status="可能需要代理",
        priority=4
    )
}


@dataclass
class DownloadProgress:
    """下载进度信息"""
    model_id: str
    current_file: str = ""
    downloaded_files: int = 0
    total_files: int = 0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    elapsed_seconds: float = 0.0
    is_complete: bool = False
    error: Optional[str] = None
    
    @property
    def progress_percent(self) -> float:
        """计算进度百分比"""
        if self.total_bytes > 0:
            return (self.downloaded_bytes / self.total_bytes) * 100
        elif self.total_files > 0:
            return (self.downloaded_files / self.total_files) * 100
        return 0.0


class ModelDownloader:
    """
    统一模型下载器
    
    功能特性：
    - 支持多镜像源自动切换
    - 断点续传
    - 进度回调
    - 错误重试
    - 单文件/全模型下载
    """
    
    def __init__(
        self,
        default_mirror: MirrorSource = MirrorSource.WISEMODEL,
        max_retries: int = 3,
        timeout: int = 600
    ):
        self.default_mirror = default_mirror
        self.max_retries = max_retries
        self.timeout = timeout
        self._current_mirror: Optional[MirrorSource] = None
        
        self._setup_hf_environment(default_mirror)
    
    def _setup_hf_environment(self, mirror: MirrorSource) -> None:
        """设置 HuggingFace 环境变量"""
        config = MIRROR_CONFIGS[mirror]
        os.environ['HF_ENDPOINT'] = config.url
        os.environ['HF_HUB_DISABLE_XSS'] = '1'
        os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '0'
        os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = str(self.timeout)
        self._current_mirror = mirror
        logger.info(f"使用镜像源: {config.name} ({config.url})")
    
    def switch_mirror(self, mirror: MirrorSource) -> None:
        """切换镜像源"""
        self._setup_hf_environment(mirror)
    
    def get_available_mirrors(self) -> List[MirrorConfig]:
        """获取可用的镜像源列表"""
        return sorted(MIRROR_CONFIGS.values(), key=lambda x: x.priority)
    
    def download_model(
        self,
        model_id: str,
        local_dir: str,
        mirror: Optional[MirrorSource] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        force_reload: bool = False,
        max_workers: int = 4
    ) -> bool:
        """
        下载完整模型
        
        Args:
            model_id: 模型ID (如 "Tongyi-MAI/Z-Image-Turbo")
            local_dir: 本地保存目录
            mirror: 指定镜像源（为None则使用默认）
            progress_callback: 进度回调函数
            force_reload: 是否强制重新下载
            max_workers: 最大并发数
            
        Returns:
            是否下载成功
        """
        if mirror:
            self.switch_mirror(mirror)
        
        if not force_reload and self._check_model_exists(local_dir):
            logger.info(f"模型已存在，跳过下载: {local_dir}")
            if progress_callback:
                progress = DownloadProgress(
                    model_id=model_id,
                    is_complete=True
                )
                progress_callback(progress)
            return True
        
        if force_reload and os.path.exists(local_dir):
            logger.info(f"移除旧目录: {local_dir}")
            shutil.rmtree(local_dir)
        
        os.makedirs(local_dir, exist_ok=True)
        
        try:
            from huggingface_hub import snapshot_download
            
            logger.info(f"开始下载模型: {model_id}")
            start_time = time.time()
            
            snapshot_download(
                repo_id=model_id,
                repo_type="model",
                local_dir=local_dir,
                local_dir_use_symlinks=False,
                resume_download=True,
                max_workers=max_workers
            )
            
            elapsed = time.time() - start_time
            logger.info(f"模型下载完成! 耗时: {elapsed/60:.1f} 分钟")
            
            if progress_callback:
                progress = DownloadProgress(
                    model_id=model_id,
                    is_complete=True,
                    elapsed_seconds=elapsed
                )
                progress_callback(progress)
            
            return True
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            
            if progress_callback:
                progress = DownloadProgress(
                    model_id=model_id,
                    error=str(e)
                )
                progress_callback(progress)
            
            return False
    
    def download_single_file(
        self,
        model_id: str,
        filename: str,
        save_dir: str,
        mirror: Optional[MirrorSource] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> Optional[str]:
        """
        下载单个文件
        
        Args:
            model_id: 模型ID
            filename: 文件名
            save_dir: 保存目录
            mirror: 指定镜像源
            progress_callback: 进度回调
            
        Returns:
            下载的文件路径，失败返回 None
        """
        if mirror:
            self.switch_mirror(mirror)
        
        os.makedirs(save_dir, exist_ok=True)
        
        try:
            from huggingface_hub import hf_hub_download
            
            logger.info(f"下载文件: {filename}")
            
            file_path = hf_hub_download(
                repo_id=model_id,
                filename=filename,
                repo_type="model",
                local_dir=save_dir,
                local_dir_use_symlinks=False
            )
            
            logger.info(f"文件下载完成: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return None
    
    def _check_model_exists(self, local_dir: str) -> bool:
        """检查模型是否已完整存在"""
        if not os.path.exists(local_dir):
            return False
        
        model_index = os.path.join(local_dir, "model_index.json")
        if os.path.exists(model_index):
            return True
        
        safetensors_files = list(Path(local_dir).glob("**/*.safetensors"))
        bin_files = list(Path(local_dir).glob("**/*.bin"))
        
        return len(safetensors_files) > 0 or len(bin_files) > 0
    
    def download_with_auto_retry(
        self,
        model_id: str,
        local_dir: str,
        mirrors: Optional[List[MirrorSource]] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> bool:
        """
        自动重试并切换镜像源下载
        
        Args:
            model_id: 模型ID
            local_dir: 本地目录
            mirrors: 要尝试的镜像源列表（按优先级）
            progress_callback: 进度回调
            
        Returns:
            是否下载成功
        """
        if mirrors is None:
            mirrors = [
                MirrorSource.WISEMODEL,
                MirrorSource.HF_MIRROR,
                MirrorSource.MODELSCOPE,
                MirrorSource.HUGGINGFACE
            ]
        
        for i, mirror in enumerate(mirrors):
            logger.info(f"尝试使用镜像源 [{i+1}/{len(mirrors)}]: {MIRROR_CONFIGS[mirror].name}")
            
            if self.download_model(
                model_id=model_id,
                local_dir=local_dir,
                mirror=mirror,
                progress_callback=progress_callback
            ):
                return True
            
            if i < len(mirrors) - 1:
                logger.info("切换到下一个镜像源...")
                time.sleep(2)
        
        logger.error("所有镜像源均下载失败")
        return False


_downloader_instance: Optional[ModelDownloader] = None


def get_model_downloader(
    default_mirror: MirrorSource = MirrorSource.WISEMODEL,
    **kwargs
) -> ModelDownloader:
    """获取下载器单例"""
    global _downloader_instance
    if _downloader_instance is None:
        _downloader_instance = ModelDownloader(default_mirror=default_mirror, **kwargs)
    return _downloader_instance


if __name__ == "__main__":
    print("\n" + "="*60)
    print("        统一模型下载器")
    print("="*60)
    
    downloader = get_model_downloader()
    
    print("\n可用镜像源:")
    for config in downloader.get_available_mirrors():
        print(f"  [{config.priority}] {config.name}")
        print(f"      URL: {config.url}")
        print(f"      速度: {config.speed}, 状态: {config.status}")
    
    print("\n" + "="*60)
    print("\n使用示例:")
    print("  from server.model_downloader import get_model_downloader, MirrorSource")
    print("  downloader = get_model_downloader()")
    print("  downloader.download_model('Tongyi-MAI/Z-Image-Turbo', './models/z-image-turbo')")
    print("  # 或使用自动重试:")
    print("  downloader.download_with_auto_retry('Tongyi-MAI/Z-Image-Turbo', './models/z-image-turbo')")
