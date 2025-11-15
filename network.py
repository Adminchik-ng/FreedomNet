import requests
import threading
from typing import List, Dict, Callable
from processor import LinkProcessor
from models import LinkItem
from config import LANG_STRINGS

class NetworkManager:
    """Управляет сетевыми операциями в отдельном потоке."""
    
    def __init__(self, status_callback: Callable, result_callback: Callable):
        """
        Args:
            status_callback (Callable): Функция для обновления статуса (принимает: message, level)
            result_callback (Callable): Функция, вызываемая по завершении (принимает: List[LinkItem])
        """
        self.status_callback = status_callback
        self.result_callback = result_callback

    def load_links_threaded(self, sources: Dict[str, List[str]]):
        """Запускает загрузку в отдельном потоке."""
        threading.Thread(target=self._load_links, args=(sources,), daemon=True).start()

    def _load_links(self, sources: Dict[str, List[str]]):
        """Рабочая функция, выполняемая в потоке."""
        all_links: List[LinkItem] = []
        
        for source_type, urls in sources.items():
            for url in urls:
                try:
                    # Сообщение отправляется на английском для последующего корректного перевода в GUI
                    self.status_callback(LANG_STRINGS["en"]["status_loading_url"].format(url=url), "info")
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    
                    new_links = LinkProcessor.parse_links(response.text, source_type)
                    all_links.extend(new_links)
                    
                    self.status_callback(LANG_STRINGS["en"]["status_ok"].format(count=len(new_links), url=url), "ok")
                except Exception as e:
                    self.status_callback(LANG_STRINGS["en"]["status_error"].format(url=url, error=e), "error")
        
        self.result_callback(all_links)