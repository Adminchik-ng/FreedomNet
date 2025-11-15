from dataclasses import dataclass

@dataclass
class LinkItem:
    """Хранит информацию о найденной ссылке."""
    link: str
    source_type: str
    scheme: str