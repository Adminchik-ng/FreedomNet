import re
import html
from typing import List, Dict, Optional, Tuple, Any
from models import LinkItem

class LinkProcessor:
    """Отвечает за парсинг и фильтрацию ссылок."""

    @staticmethod
    def parse_links(text: str, source_type: str) -> List[LinkItem]:
        """Парсит ссылки по схемам (vless, vmess, trojan, shadowsocks, ss, hysteria2)."""
        # Экранируем HTML сущности перед парсингом, чтобы ссылки из Яндекса читались корректно
        text = html.unescape(text)
        
        # Обновленный паттерн с hysteria2 и ограничением на кавычки/скобки, чтобы не захватывать HTML теги
        pattern = r"(?:vless|vmess|trojan|shadowsocks|ss|hysteria2)://[^\s\"\'<>]+"
        found_links = re.findall(pattern, text)
        
        # Удаляем дубликаты с сохранением порядка
        unique_links = list(dict.fromkeys(found_links))
        links = []

        for link in unique_links:
            try:
                raw_scheme = link.split("://")[0].lower()
                scheme = "shadowsocks" if raw_scheme == "ss" else raw_scheme
                links.append(LinkItem(link=link.strip(), source_type=source_type, scheme=scheme))
            except (IndexError, AttributeError):
                continue
        return links

    @staticmethod
    def _port_matches(link: str, port_filter: str) -> bool:
        """Проверяет, соответствует ли порт ссылки фильтру (одно значение или диапазон)."""
        # Hysteria2 и другие протоколы могут указывать порты аналогичным образом в виде :PORT
        m = re.search(r":(\d+)", link)
        if not m:
            return False
        
        try:
            port = int(m.group(1))
            if "-" in port_filter:
                start, end = map(int, port_filter.split("-"))
                return start <= port <= end
            else:
                return port == int(port_filter)
        except ValueError:
            return False

    @staticmethod
    def filter_links(links: List[LinkItem], filters: Dict[str, str]) -> Tuple[List[LinkItem], Optional[str]]:
        """
        Фильтрует список ссылок на основе словаря фильтров.
        Возвращает (отфильтрованный_список, сообщение_об_ошибке)
        """
        filtered = links
        
        scheme_filter = filters.get("scheme", "")
        if scheme_filter and scheme_filter != filters.get("all_schemes_str"):
            filtered = [l for l in filtered if l.scheme.lower() == scheme_filter.lower()]

        type_filter = filters.get("type", "")
        if type_filter and type_filter != filters.get("all_types_str"):
            filtered = [l for l in filtered if l.source_type == type_filter]

        port_filter = filters.get("port", "")
        if port_filter:
            try:
                filtered = [l for l in filtered if LinkProcessor._port_matches(l.link, port_filter)]
            except Exception as e:
                return ([], f"Port Filter Error: {e}")

        sni_filter = filters.get("sni_value", "")
        if sni_filter:
            # RegEx для извлечения значения из &sni=... или ?sni=...
            sni_regex_extractor = r"(?:[?&]sni=([^&#]+))"
            new_filtered = []
            for l in filtered:
                match = re.search(sni_regex_extractor, l.link, re.IGNORECASE)
                # Проверяем частичное совпадение
                if match and sni_filter.lower() in match.group(1).lower():
                    new_filtered.append(l)
            filtered = new_filtered
            
        ip_filter = filters.get("ip", "")
        if ip_filter:
            try:
                # Ищет IP после @
                filtered = [l for l in filtered if re.search(rf"@{re.escape(ip_filter)}", l.link)]
            except re.error as e:
                return ([], f"RegEx Error: {e}")

        generic_filter = filters.get("generic_search", "")
        if generic_filter:
            filtered = [l for l in filtered if generic_filter.lower() in l.link.lower()]

        return (filtered, None)