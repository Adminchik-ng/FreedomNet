import asyncio
import threading
import random
from typing import List, Dict, Callable, Any
from curl_cffi.requests import AsyncSession
from processor import LinkProcessor
from models import LinkItem
from config import LANG_STRINGS

class NetworkManager:
    """Управляет сетевыми операциями. В мобильном режиме обходит блокировки, в проводном - работает на максимальной скорости."""
    
    def __init__(self, status_callback: Callable, result_callback: Callable):
        """
        Args:
            status_callback (Callable): Функция для обновления статуса
            result_callback (Callable): Функция, вызываемая по завершении
        """
        self.status_callback = status_callback
        self.result_callback = result_callback

    def load_links_threaded(self, sources_to_load: List[Dict[str, str]], is_mobile: bool = True):
        """Запускает асинхронную загрузку в отдельном фоновом потоке."""
        threading.Thread(target=self._run_async_loop, args=(sources_to_load, is_mobile), daemon=True).start()

    def _run_async_loop(self, sources_to_load: List[Dict[str, str]], is_mobile: bool):
        """Служебный метод для создания и запуска event loop в потоке."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._load_links_async(sources_to_load, is_mobile))
        finally:
            loop.close()

    async def _fetch_and_parse_mobile(self, source: Dict[str, str], all_links: List[LinkItem]):
        url = source["url"]
        name = source["name"]
        source_type = source["type"]

        self.status_callback(LANG_STRINGS["en"]["status_loading_url"].format(url=name), "info")
        try:
            # Используем самые стабильные отпечатки, которые редко попадают на капчу
            impersonate_targets = ["chrome120", "chrome124", "edge101", "safari15_3", "safari17_0"]
            target = random.choice(impersonate_targets)
            
            # Полностью убираем кастомные заголовки, чтобы не ломать HTTP/2 фреймы и порядок заголовков,
            # которые curl_cffi генерирует идеально под браузер. Это скрывает любые "следы питона/скрипта".
            async with AsyncSession(impersonate=target) as session:
                response = await session.get(url, timeout=30)
                text = response.text

            # Проверяем капчу ДО того как упадем с потенциальным HTTP 403/503
            if "<title>Вы не робот?</title>" in text or "smartCaptchaHost" in text or "showcaptcha" in str(response.url):
                self.status_callback(name, "captcha")
                return
            
            response.raise_for_status()

            new_links = LinkProcessor.parse_links(text, source_type)
            all_links.extend(new_links)
            self.status_callback(LANG_STRINGS["en"]["status_ok"].format(count=len(new_links), name=name), "ok")
        except Exception as e:
            self.status_callback(LANG_STRINGS["en"]["status_error"].format(name=name, error=str(e)), "error")

    async def _fetch_and_parse_wired(self, session: AsyncSession, sem: asyncio.Semaphore, source: Dict[str, str], all_links: List[LinkItem]):
        url = source["url"]
        name = source["name"]
        source_type = source["type"]

        async with sem:
            self.status_callback(LANG_STRINGS["en"]["status_loading_url"].format(url=name), "info")
            try:
                # Так же убираем любые кастомные заголовки из проводного режима
                response = await session.get(url, timeout=20)
                text = response.text

                # Проверка на капчу до raise_for_status
                if "<title>Вы не робот?</title>" in text or "smartCaptchaHost" in text or "showcaptcha" in str(response.url):
                    self.status_callback(name, "captcha")
                    return

                response.raise_for_status()

                new_links = LinkProcessor.parse_links(text, source_type)
                all_links.extend(new_links)
                self.status_callback(LANG_STRINGS["en"]["status_ok"].format(count=len(new_links), name=name), "ok")
            except Exception as e:
                self.status_callback(LANG_STRINGS["en"]["status_error"].format(name=name, error=str(e)), "error")

    async def _load_links_async(self, sources_to_load: List[Dict[str, str]], is_mobile: bool):
        """Асинхронная рабочая функция для загрузки всех ссылок."""
        all_links: List[LinkItem] = []
        
        if is_mobile:
            tasks = []
            for s in sources_to_load:
                task = asyncio.create_task(self._fetch_and_parse_mobile(s, all_links))
                tasks.append(task)
                await asyncio.sleep(1.0) # Запускаем по одной с интервалом 1 сек
            
            if tasks:
                await asyncio.gather(*tasks)
        else:
            sem = asyncio.Semaphore(15) # Снижено с 50 до 15. Это оптимальнее для избежания бана и капчи
            # Асинхронка с HTTPX (aiohttp палится на уровне TLS)
            target = random.choice(["chrome120", "chrome124", "edge101", "safari17_0"])
            async with AsyncSession(impersonate=target) as session:
                tasks = [self._fetch_and_parse_wired(session, sem, s, all_links) for s in sources_to_load]
                await asyncio.gather(*tasks)
            
        self.result_callback(all_links)