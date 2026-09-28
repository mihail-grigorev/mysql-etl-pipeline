from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

# Все виды дефисов и тире
DASHES = "-‐‑‒–—―−"

# Гомоглифы (буквы-двойники кириллицы и латиницы)
HOMOGLYPHS = {
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
    'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O',
    'Р': 'P', 'С': 'C', 'Т': 'T', 'Х': 'X', 'і': 'i', 'І': 'I'
}

# Титулы, обращения, звания, приставки вежливости (Russian & English)
HONORIFICS_PREFIXES = {
    # Русские обращения
    "господин", "госпожа", "г-н", "г-жа", "гн", "гжа",
    "товарищ", "тов", "тов.",
    "гражданин", "гражданка", "гр", "гр.", "гр-н", "гр-ка", "грн",
    "доктор", "др", "др.", "д-р",
    "профессор", "проф", "проф.",
    "академик", "акад", "акад.",
    "доцент", "доц", "доц.",
    "сэр", "мистер", "миссис", "мисс", "мадам", "мадемуазель",
    "коллега", "уважаемый", "уважаемая",
    "отец", "священник", "иерей", "протоиерей", "владыка", "епископ", "митрополит",
    "майор", "капитан", "генерал", "полковник", "лейтенант",
    "инженер", "эксперт", "бакалавр", "магистр",
    # English / International
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss", "dr", "dr.", "prof", "prof.",
    "sir", "lord", "lady", "dame", "madam", "madame", "monsieur", "m.", "mme",
    "rev", "rev.", "fr", "fr.", "father", "pastor",
    "capt", "capt.", "col", "col.", "gen", "gen.", "sgt", "hon", "hon.",
    "comrade", "herr", "frau"
}

HONORIFICS_POSTFIXES = {
    "младший", "старший", "мл.", "ст.", "мл", "ст",
    "jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v",
    "esq", "esq.", "phd", "ph.d.", "md", "m.d.", "mba"
}

# Иностранные дворянские и родовые приставки к фамилиям
# Многокомпонентные приставки (сортируются по длине при поиске)
FOREIGN_PREFIXES_MULTI = [
    "фон дер", "фон унд цу", "ван дер", "ван ден", "ван де",
    "де ла", "де лос", "де лас",
    "von der", "von und zu", "van der", "van den", "van de",
    "de la", "de los", "de las", "de le"
]

# Одиночные приставки
FOREIGN_PREFIXES_SINGLE = {
    # Немецкие
    "фон", "цу", "фом", "von", "zu", "vom",
    # Нидерландские / Фламандские
    "ван", "тер", "тен", "van", "ter", "ten",
    # Французские / Испанские / Португальские / Итальянские
    "де", "дю", "дез", "ле", "ла", "дель", "делла", "деи", "дельи", "делле",
    "ди", "да", "до", "дос", "дас",
    "de", "du", "des", "le", "la", "les", "del", "della", "dei", "degli", "delle",
    "di", "da", "do", "dos", "das", "d'", "д'",
    # Арабские / Семитские
    "аль", "эль", "ибн", "бин", "бен", "абу",
    "al", "el", "ibn", "bin", "ben", "abu",
    # Кельтские / Ирландские / Шотландские
    "о'", "мак", "фитц",
    "o'", "mc", "mac", "fitz",
    # Сан / Сен / Святой
    "сан", "санта", "санто", "сен", "сент", "st", "st.", "saint"
}

# Этимологические гнезда имён (Однокоренные / исторически тождественные)
# "юрий, георгий и егор например одно и то же имя потому что происходит от одного"
ETYMOLOGY_CLUSTERS: List[Dict[str, any]] = [
    {
        "root": "georgios",
        "canonical": "Георгий",
        "variants": {
            "георгий", "юрий", "егор", "george", "georg", "jorge", "giorgio", "georges",
            "жора", "гоша", "горя", "юрик", "юра", "егорушка", "егорка",
            "georgiy", "georgy", "yuri", "yury", "egor", "iuri"
        }
    },
    {
        "root": "ioannes",
        "canonical": "Иван",
        "variants": {
            "иван", "ян", "иоанн", "john", "jean", "juan", "johan", "johann", "giovanni",
            "ваня", "ванечка", "ванюша", "янка", "янчик",
            "ivan", "ian", "jan", "sean", "shawn", "evan", "hans"
        }
    },
    {
        "root": "alexandros",
        "canonical": "Александр",
        "variants": {
            "александр", "александра", "алекс", "саша", "шура", "санек", "санька",
            "alexander", "alex", "alexandre", "alessandro", "alejandro", "sasha",
            "oleksandr", "aleksandr"
        }
    },
    {
        "root": "dimitrios",
        "canonical": "Дмитрий",
        "variants": {
            "дмитрий", "димитрий", "митя", "дима", "димка", "митюша",
            "dmitry", "dmitriy", "dmitri", "demetrius", "dimitri"
        }
    },
    {
        "root": "nikolaos",
        "canonical": "Николай",
        "variants": {
            "николай", "коля", "коленька", "клаус", "николас", "николя", "микола",
            "nicholas", "nick", "nicolas", "klaus", "nikolai", "nikolay"
        }
    },
    {
        "root": "michael",
        "canonical": "Михаил",
        "variants": {
            "михаил", "миша", "мишенька", "мишель", "майкл", "мигель", "микеле",
            "mikhail", "michael", "michel", "miguel", "michele", "mike"
        }
    },
    {
        "root": "petros",
        "canonical": "Петр",
        "variants": {
            "петр", "пётр", "петя", "петенька", "питер", "пьер", "педро", "пьетро",
            "peter", "pyotr", "petr", "pierre", "pedro", "pietro"
        }
    },
    {
        "root": "paulos",
        "canonical": "Павел",
        "variants": {
            "павел", "паша", "павлик", "пол", "пабло", "паоло",
            "pavel", "paul", "pablo", "paolo"
        }
    },
    {
        "root": "andreas",
        "canonical": "Андрей",
        "variants": {
            "андрей", "анджей", "эндрю", "анри", "андри", "андрюша",
            "andrey", "andrei", "andrew", "andre", "andreas"
        }
    },
    {
        "root": "danilos",
        "canonical": "Даниил",
        "variants": {
            "даниил", "данила", "данил", "даниэль", "дэниэл", "даня",
            "daniil", "danila", "daniel", "dan", "danny"
        }
    },
    {
        "root": "theodoros",
        "canonical": "Федор",
        "variants": {
            "федор", "фёдор", "федя", "теодор", "тэодор", "тео",
            "fyodor", "fedor", "theodore", "theo"
        }
    },
    {
        "root": "stephanos",
        "canonical": "Степан",
        "variants": {
            "степан", "степа", "стёпа", "стефан", "стивен", "эстебан",
            "stepan", "stefan", "stephen", "steve", "esteban"
        }
    },
    {
        "root": "vasilios",
        "canonical": "Василий",
        "variants": {
            "василий", "вася", "василек", "бэзил", "базиль", "василь",
            "vasily", "vasiliy", "basil", "basile"
        }
    },
    {
        "root": "konstantinos",
        "canonical": "Константин",
        "variants": {
            "константин", "костя", "костик", "константинос",
            "konstantin", "constantine", "costa"
        }
    },
    {
        "root": "alexeios",
        "canonical": "Алексей",
        "variants": {
            "алексей", "алексий", "леша", "лёша", "алёша", "алеша",
            "aleksey", "alexey", "alexis"
        }
    },
    {
        "root": "helena",
        "canonical": "Елена",
        "variants": {
            "елена", "алёна", "алена", "лена", "леночка", "илона", "хелен", "элен",
            "elena", "alena", "helen", "helene", "ilona", "ellen"
        }
    },
    {
        "root": "xenia",
        "canonical": "Ксения",
        "variants": {
            "ксения", "оксана", "аксинья", "ксюша", "ксенечка",
            "ksenia", "oxana", "oksana", "axinya", "xenia"
        }
    },
    {
        "root": "katerina",
        "canonical": "Екатерина",
        "variants": {
            "екатерина", "катерина", "катя", "катюша", "кэтлин", "кэтрин",
            "ekaterina", "katerina", "catherine", "katherine", "kate"
        }
    },
    {
        "root": "anna",
        "canonical": "Анна",
        "variants": {
            "анна", "аня", "анюта", "ханна", "энн", "анета",
            "anna", "ann", "anne", "hannah"
        }
    },
    {
        "root": "maria",
        "canonical": "Мария",
        "variants": {
            "мария", "марья", "маша", "машенька", "мэри", "мари",
            "maria", "mary", "marie", "marya"
        }
    },
    {
        "root": "elizabeth",
        "canonical": "Елизавета",
        "variants": {
            "елизавета", "лиза", "лизонька", "элизабет", "бетти",
            "elizaveta", "elizabeth", "lisa"
        }
    },
    {
        "root": "sophia",
        "canonical": "София",
        "variants": {
            "софия", "софья", "соня", "сонечка",
            "sophia", "sofia", "sonia", "sonya"
        }
    },
    {
        "root": "daria",
        "canonical": "Дарья",
        "variants": {
            "дарья", "дария", "даша", "дашенька",
            "daria", "darya"
        }
    },
    {
        "root": "tatiana",
        "canonical": "Татьяна",
        "variants": {
            "татьяна", "таня", "танечка",
            "tatiana", "tatyana", "tanya"
        }
    },
    {
        "root": "natalia",
        "canonical": "Наталья",
        "variants": {
            "наталья", "наталия", "наташа",
            "natalia", "natalya", "natasha"
        }
    },
    {
        "root": "eugene",
        "canonical": "Евгений",
        "variants": {
            "евгений", "евгения", "женя", "эжен",
            "eugene", "evgeny", "evgeniy", "eugenia"
        }
    },
    {
        "root": "grigory",
        "canonical": "Григорий",
        "variants": {
            "григорий", "гриша", "грегори",
            "grigory", "grigori", "gregory"
        }
    },
    {
        "root": "sergey",
        "canonical": "Сергей",
        "variants": {
            "сергей", "серёжа", "сережа", "серж",
            "sergey", "sergei", "serge"
        }
    },
    {
        "root": "roman",
        "canonical": "Роман",
        "variants": {
            "роман", "рома", "ромочка", "roman"
        }
    },
    {
        "root": "maxim",
        "canonical": "Максим",
        "variants": {
            "максим", "макс", "maxim", "max"
        }
    },
    {
        "root": "anton",
        "canonical": "Антон",
        "variants": {
            "антон", "тоша", "энтони", "антонио",
            "anton", "anthony", "antonio"
        }
    },
    {
        "root": "filippos",
        "canonical": "Филипп",
        "variants": {
            "филипп", "филя", "philip", "philippe", "felipe"
        }
    },
    {
        "root": "matthew",
        "canonical": "Матвей",
        "variants": {
            "матвей", "мотя", "мэтью", "маттео",
            "matvey", "matthew", "matteo"
        }
    },
    {
        "root": "thomas",
        "canonical": "Фома",
        "variants": {
            "фома", "томас", "том", "thomas", "tom"
        }
    },
    {
        "root": "victor",
        "canonical": "Виктор",
        "variants": {
            "виктор", "витя", "victor", "viktor"
        }
    },
    {
        "root": "vladimir",
        "canonical": "Владимир",
        "variants": {
            "владимир", "володя", "вова", "vladimir", "wladimir"
        }
    }
]

# Карта от любого варианта имени к его этимологическому корню и каноническому имени
NAME_TO_ETYMOLOGY: Dict[str, Tuple[str, str]] = {}
for cluster in ETYMOLOGY_CLUSTERS:
    r = cluster["root"]
    c = cluster["canonical"]
    for v in cluster["variants"]:
        NAME_TO_ETYMOLOGY[v.lower().replace("ё", "е")] = (r, c)

def get_name_etymology_root(name: str) -> Optional[str]:
    """Возвращает идентификатор этимологического корня имени."""
    cleaned = re.sub(r"[^а-яa-z]", "", name.lower().replace("ё", "е"))
    if cleaned in NAME_TO_ETYMOLOGY:
        return NAME_TO_ETYMOLOGY[cleaned][0]
    return None

def are_names_etymologically_identical(name1: str, name2: str) -> bool:
    """
    Проверяет, являются ли два имени этимологически тождественными
    (например, Юрий и Георгий, Иван и Ян, Оксана и Ксения).
    """
    r1 = get_name_etymology_root(name1)
    r2 = get_name_etymology_root(name2)
    if r1 and r2 and r1 == r2:
        return True
    return False

# Имена и Отчества (Мужские и Женские)
MALE_FIRST: Dict[str, Tuple[str, str]] = {
    "Александр": ("Александрович", "Александровна"),
    "Алексей": ("Алексеевич", "Алексеевна"),
    "Анатолий": ("Анатольевич", "Анатольевна"),
    "Андрей": ("Андреевич", "Андреевна"),
    "Антон": ("Антонович", "Антоновна"),
    "Артем": ("Артемович", "Артемовна"),
    "Артур": ("Артурович", "Артуровна"),
    "Борис": ("Борисович", "Борисовна"),
    "Вадим": ("Вадимович", "Вадимовна"),
    "Валентин": ("Валентинович", "Валентиновна"),
    "Валерий": ("Валерьевич", "Валерьевна"),
    "Василий": ("Васильевич", "Васильевна"),
    "Виктор": ("Викторович", "Викторовна"),
    "Виталий": ("Витальевич", "Витальевна"),
    "Владимир": ("Владимирович", "Владимировна"),
    "Владислав": ("Владиславович", "Владиславовна"),
    "Вячеслав": ("Вячеславович", "Вячеславовна"),
    "Геннадий": ("Геннадьевич", "Геннадьевна"),
    "Георгий": ("Георгиевич", "Георгиевна"),
    "Григорий": ("Григорьевич", "Григорьевна"),
    "Даниил": ("Даниилович", "Данииловна"),
    "Денис": ("Денисович", "Денисовна"),
    "Дмитрий": ("Дмитриевич", "Дмитриевна"),
    "Евгений": ("Евгеньевич", "Евгеньевна"),
    "Егор": ("Егорович", "Егоровна"),
    "Иван": ("Иванович", "Ивановна"),
    "Игорь": ("Игоревич", "Игоревна"),
    "Илья": ("Ильич", "Ильинична"),
    "Кирилл": ("Кириллович", "Кирилловна"),
    "Константин": ("Константинович", "Константиновна"),
    "Лев": ("Львович", "Львовна"),
    "Леонид": ("Леонидович", "Леонидовна"),
    "Максим": ("Максимович", "Максимовна"),
    "Матвей": ("Матвеевич", "Матвеевна"),
    "Михаил": ("Михайлович", "Михайловна"),
    "Никита": ("Никитич", "Никитична"),
    "Николай": ("Николаевич", "Николаевна"),
    "Олег": ("Олегович", "Олеговна"),
    "Павел": ("Павлович", "Павловна"),
    "Петр": ("Петрович", "Петровна"),
    "Роман": ("Романович", "Романовна"),
    "Руслан": ("Русланович", "Руслановна"),
    "Сергей": ("Сергеевич", "Сергеевна"),
    "Станислав": ("Станиславович", "Станиславовна"),
    "Степан": ("Степанович", "Степановна"),
    "Тимофей": ("Тимофеевич", "Тимофеевна"),
    "Федор": ("Федорович", "Федоровна"),
    "Филипп": ("Филиппович", "Филипповна"),
    "Эдуард": ("Эдуардович", "Эдуардовна"),
    "Юрий": ("Юрьевич", "Юрьевна"),
    "Ярослав": ("Ярославович", "Ярославовна"),
    # Иностранные мужские имена (часто без классических отчеств)
    "Людвиг": ("Людвигович", "Людвиговна"),
    "Наполеон": ("Наполеонович", "Наполеоновна"),
    "Фридрих": ("Фридрихович", "Фридриховна"),
    "Вильгельм": ("Вильгельмович", "Вильгельмовна"),
    "Урсула": ("Урсулович", "Урсуловна"),
    "Шарль": ("Шарлевич", "Шарлевна"),
    "Жан": ("Жанович", "Жановна"),
    "Луи": ("Луисович", "Луисовна"),
    "Поль": ("Полевич", "Полевна"),
    "Карл": ("Карлович", "Карловна"),
    "Хайнц": ("Хайнцевич", "Хайнцевна"),
    "Иоганн": ("Иоганнович", "Иоганновна"),
    "Себастьян": ("Себастьянович", "Себастьяновна"),
    "Джордж": ("Джорджевич", "Джорджевна"),
    "Майкл": ("Майклович", "Майкловна"),
    "Антуан": ("Антуанович", "Антуановна")
}

FEMALE_FIRST: List[str] = [
    "Александра", "Алена", "Алина", "Алиса", "Алла", "Анастасия", "Ангелина", "Анна",
    "Валентина", "Валерия", "Вера", "Вероника", "Виктория", "Галина", "Дарья", "Диана",
    "Евгения", "Екатерина", "Елена", "Елизавета", "Жанна", "Инна", "Ирина", "Кристина",
    "Ксения", "Лариса", "Лидия", "Любовь", "Людмила", "Маргарита", "Марина", "Мария",
    "Надежда", "Наталья", "Нина", "Оксана", "Олеся", "Ольга", "Полина", "Светлана",
    "Снежана", "София", "Тамара", "Татьяна", "Ульяна", "Юлия", "Яна",
    # Иностранные женские имена
    "Урсула", "Мари", "Тереза", "Антуанетта", "Клэр", "Эмма", "Шарлотта"
]

# Уменьшительно-ласкательные формы / Никнеймы
NICKNAMES: Dict[str, str] = {
    "Александр": "Саша", "Александра": "Саша", "Алексей": "Леша", "Анатолий": "Толя",
    "Андрей": "Андрюша", "Антон": "Тоша", "Борис": "Боря", "Валентин": "Валя",
    "Валерий": "Валера", "Василий": "Вася", "Виктор": "Витя", "Владимир": "Вова",
    "Владислав": "Влад", "Вячеслав": "Слава", "Георгий": "Жора", "Юрий": "Юра",
    "Егор": "Егорка", "Григорий": "Гриша", "Даниил": "Даня", "Денис": "Деня",
    "Дмитрий": "Дима", "Евгений": "Женя", "Евгения": "Женя", "Иван": "Ваня",
    "Илья": "Илюша", "Константин": "Костя", "Леонид": "Леня", "Максим": "Макс",
    "Михаил": "Миша", "Николай": "Коля", "Павел": "Паша", "Петр": "Петя",
    "Роман": "Рома", "Сергей": "Сережа", "Степан": "Степа", "Тимофей": "Тима",
    "Федор": "Федя", "Филипп": "Филя", "Анна": "Аня", "Анастасия": "Настя",
    "Дарья": "Даша", "Екатерина": "Катя", "Елена": "Лена", "Елизавета": "Лиза",
    "Ксения": "Ксюша", "Оксана": "Ксюша", "Мария": "Маша", "Наталья": "Наташа",
    "Ольга": "Оля", "Полина": "Поля", "Светлана": "Света", "Татьяна": "Таня",
    "Юлия": "Юля"
}

# Справочник фамилий (включая русские, иностранные с приставками и составные)
SURNAMES: List[str] = [
    # Русские стандартные фамилии (-ов, -ев, -ин, -ский)
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов",
    "Новиков", "Федоров", "Морозов", "Волков", "Алексеев", "Лебедев", "Семенов", "Егоров",
    "Павлов", "Козлов", "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Никитин",
    "Захаров", "Зайцев", "Соловьев", "Борисов", "Яковлев", "Григорьев", "Романов", "Воробьев",
    "Сергеев", "Кузьмин", "Фролов", "Александров", "Дмитриев", "Королев", "Гусев", "Киселев",
    "Ильин", "Максимов", "Поляков", "Сорокин", "Виноградов", "Ковалев", "Белов", "Медведев",
    "Антонов", "Тарасов", "Беляев", "Трофимов", "Давыдов", "Титов", "Белоусов", "Ширяев",
    # Фамилии на -ский/-цкий
    "Ковалевский", "Островский", "Вяземский", "Чайковский", "Полонский", "Завадовский",
    # Двойные составные фамилии
    "Мамин-Сибиряк", "Римский-Корсаков", "Салтыков-Щедрин", "Мусин-Пушкин", "Миклухо-Маклай",
    "Немирович-Данченко", "Голенищев-Кутузов", "Новиков-Прибой",
    # Иностранные фамилии с благородными и родовыми приставками
    "ван Бетховен", "де Голль", "фон дер Ляйен", "де Сен-Экзюпери", "ван Дейк",
    "фон Бисмарк", "ди Каприо", "да Винчи", "аль-Мансур", "де ла Хойя", "д'Артаньян",
    # Иностранные фамилии без приставок
    "Смит", "Миллер", "Тейлор", "Браун", "Уилсон", "Шмидт", "Вебер", "Мюллер"
]

# Грамматическое склонение и определение женских форм фамилий
def to_female(surname: str) -> str:
    """Генерирует женскую форму фамилии."""
    # Если фамилия содержит дефис (составная), обрабатываем части
    if "-" in surname:
        return "-".join(to_female(part) for part in surname.split("-"))
    # Если фамилия содержит иностранную приставку (например "ван Бетховен")
    parts = surname.split()
    if len(parts) > 1:
        # Приставки неизменны, меняется только коренная часть
        prefix = " ".join(parts[:-1])
        base = to_female(parts[-1])
        return f"{prefix} {base}"

    s = surname
    if s.endswith(("ов", "ев", "ин", "ын")):
        return s + "а"
    if s.endswith("ский"):
        return s[:-4] + "ская"
    if s.endswith("цкий"):
        return s[:-4] + "цкая"
    if s.endswith("ый"):
        return s[:-2] + "ая"
    if s.endswith("ой"):
        return s[:-2] + "ая"
    # Иностранные и несклоняемые (-ко, -енко, -их, -ых, -дзе, -швили, -ян, Смит и т.д.)
    return s

def to_male_lemma(surname: str) -> str:
    """Приводит женскую форму фамилии к базовой мужской лемме для сравнения."""
    if "-" in surname:
        return "-".join(to_male_lemma(part) for part in surname.split("-"))
    parts = surname.split()
    if len(parts) > 1:
        prefix = " ".join(parts[:-1])
        base = to_male_lemma(parts[-1])
        return f"{prefix} {base}"

    s = surname
    if s.endswith(("ова", "ева", "ина", "ына")):
        return s[:-1]
    if s.endswith("ская"):
        return s[:-4] + "ский"
    if s.endswith("цкая"):
        return s[:-4] + "цкий"
    if s.endswith("ая"):
        return s[:-2] + "ый"
    return s

def canonical_from_parts(last: str, first: str, middle: str = "") -> str:
    """Формирует каноническую строку ФИО."""
    parts = [last.strip(), first.strip()]
    if middle and middle.strip():
        parts.append(middle.strip())
    return " ".join(parts)

def match_key(last: str, first: str, middle: str = "") -> str:
    """Генерирует нормализованный ключ сопоставления match_key."""
    def clean(w: str) -> str:
        s = unicodedata.normalize("NFKC", w).lower()
        s = s.replace("ё", "е")
        return re.sub(r"[^а-яa-z0-9]", "", s)
    
    l_key = clean(to_male_lemma(last))
    # Если имя имеет этимологический корень, используем его для ключа
    f_root = get_name_etymology_root(first) or clean(first)
    m_root = clean(middle)
    return f"{l_key}|{f_root}|{m_root}"

# Генерация данных (датакласс Person, генерация тестовых персон)
@dataclass
class Person:
    last: str
    first: str
    middle: str | None
    canonical: str
    gender: str  # 'M' or 'F'
    honorific: str | None = None
    has_foreign_prefix: bool = False
    multi_first_count: int = 1  # 1, 2, 3, 4
    etymology_root: str | None = None

def generate_people(n: int, rng) -> List[Person]:
    """Генерирует n репрезентативных персон с разнообразными типами ФИО."""
    people: List[Person] = []
    male_names = list(MALE_FIRST.keys())
    female_names = list(FEMALE_FIRST)

    # 1. Заранее подготавливаем несколько специальных сложных кейсов:
    # - Кейс этимологических близнецов (Георгий / Юрий / Егор)
    # - Кейс иностранных дворянских фамилий с приставками
    # - Кейс многосоставных имён (двойные, тройные, четверные)
    # - Кейс составных русских фамилий
    
    special_cases = [
        # (Фамилия, Имя, Отчество, Пол, Приставка, Мульти-имя, Корень)
        ("Бетховен", "Людвиг", None, "M", "ван", 1, None),
        ("Ляйен", "Урсула", None, "F", "фон дер", 1, None),
        ("Голль", "Шарль", None, "M", "де", 1, None),
        ("Сент-Экзюпери", "Антуан", "Мари", "M", "де", 2, None),
        ("Бах", "Иоганн Себастьян", None, "M", None, 2, "ioannes"),
        ("Бонапарт", "Шарль Луи Наполеон", None, "M", None, 3, None),
        ("Нойвирт", "Карл Хайнц Фридрих Вильгельм", None, "M", None, 4, None),
        ("Смирнова", "Анна-Мария", "Ивановна", "F", None, 2, "anna"),
        ("Мамин-Сибиряк", "Дмитрий", "Наркисович", "M", None, 1, "dimitrios"),
        ("Римский-Корсаков", "Николай", "Андреевич", "M", None, 1, "nikolaos"),
        ("Егоров", "Юрий", "Георгиевич", "M", None, 1, "georgios"),
        ("Кузнецов", "Георгий", "Егорович", "M", None, 1, "georgios"),
        ("Васильев", "Егор", "Юрьевич", "M", None, 1, "georgios"),
        ("Попова", "Оксана", "Сергеевна", "F", None, 1, "xenia"),
        ("Федоров", "Иван", "Янович", "M", None, 1, "ioannes")
    ]

    for s_last, s_first, s_mid, s_gen, s_pfx, s_cnt, s_etym in special_cases:
        full_last = f"{s_pfx} {s_last}" if s_pfx else s_last
        canon = canonical_from_parts(full_last, s_first, s_mid or "")
        people.append(Person(
            last=full_last,
            first=s_first,
            middle=s_mid,
            canonical=canon,
            gender=s_gen,
            has_foreign_prefix=bool(s_pfx),
            multi_first_count=s_cnt,
            etymology_root=s_etym or get_name_etymology_root(s_first)
        ))

    # Добиваем оставшееся количество до n
    base_surnames = list(SURNAMES)
    while len(people) < n:
        gender = "M" if rng.random() < 0.55 else "F"
        surn = rng.choice(base_surnames)
        if gender == "F":
            surn = to_female(surn)

        if gender == "M":
            fname = rng.choice(male_names)
            m_base = rng.choice(male_names)
            patr = MALE_FIRST[m_base][0]
        else:
            fname = rng.choice(female_names)
            m_base = rng.choice(male_names)
            patr = MALE_FIRST[m_base][1]

        # Иногда делаем двойное имя (например, Анна-Мария или Жан-Поль)
        multi_cnt = 1
        if rng.random() < 0.15:
            multi_cnt = 2
            second_name = rng.choice(female_names if gender == "F" else male_names)
            fname = f"{fname}-{second_name}"

        canon = canonical_from_parts(surn, fname, patr)
        people.append(Person(
            last=surn,
            first=fname,
            middle=patr,
            canonical=canon,
            gender=gender,
            has_foreign_prefix=" " in surn,
            multi_first_count=multi_cnt,
            etymology_root=get_name_etymology_root(fname.split("-")[0])
        ))

    return people[:n]

# Варианты искажений и написаний для стресс-тестирования ETL
@dataclass
class Variant:
    code: str
    description: str

VARIANTS = [
    Variant("exact", "Точное каноническое написание (Фамилия Имя Отчество)"),
    Variant("reverse_order", "Обратный порядок (Имя Отчество Фамилия)"),
    Variant("first_last", "Только имя и фамилия (Имя Фамилия)"),
    Variant("last_first", "Только фамилия и имя (Фамилия Имя)"),
    Variant("initials_full", "Фамилия с полными инициалами (Фамилия И.О.)"),
    Variant("initials_first_only", "Фамилия только с первым инициалом (Фамилия И.)"),
    Variant("initials_prefix", "Инициалы перед фамилией (И.О. Фамилия)"),
    Variant("honorific_title", "С титулом/обращением (господин / тов. / Dr. / проф.)"),
    Variant("translit_en", "Полная транслитерация на английский язык (Latin script)"),
    Variant("etymology_cognate", "Замена на этимологический аналог (Юрий <-> Георгий <-> Егор)"),
    Variant("foreign_prefix_variation", "Искажение иностранной приставки (слитно / дефис / регистр)"),
    Variant("compound_multi_name", "Сложное многосоставное имя (двойное / тройное / без дефиса)"),
    Variant("homoglyph_mixed", "Буквы-двойники кириллицы/латиницы внутри слов"),
    Variant("typo_levenshtein", "Опечатка (перестановка букв / пропуск буквы)"),
    Variant("keyboard_layout", "Случайная смена раскладки клавиатуры (qwerty <-> йцукен)")
]

def assign_variants(slots: List[Tuple[int, int]], people: List[Person], rng) -> Dict[Tuple[int, int], Variant]:
    """Назначает правила отображения каждому слоту персоны в источниках."""
    assigned = {}
    var_list = list(VARIANTS)
    
    for (person_idx, src_idx) in slots:
        p = people[person_idx]
        if src_idx == 0:
            # В источнике 1 (src_projects) чаще держим чистые или англоязычные/обратные формы
            choices = [v for v in var_list if v.code in (
                "exact", "first_last", "reverse_order", "translit_en", "honorific_title",
                "compound_multi_name", "foreign_prefix_variation"
            )]
        else:
            # В источнике 2 (src_hr) чаще генерируем сложные проверки:
            # этимологию, опечатки, инициалы, титулы, омоглифы
            choices = [v for v in var_list if v.code in (
                "exact", "initials_full", "initials_first_only", "etymology_cognate",
                "honorific_title", "homoglyph_mixed", "typo_levenshtein", "keyboard_layout",
                "foreign_prefix_variation"
            )]
        
        # Если у человека есть этимологический корень Георгий/Юрий/Егор, обязательно проверяем его
        if p.etymology_root in ("georgios", "ioannes", "xenia") and src_idx == 1 and rng.random() < 0.7:
            assigned[(person_idx, src_idx)] = next(v for v in var_list if v.code == "etymology_cognate")
        elif p.has_foreign_prefix and rng.random() < 0.6:
            assigned[(person_idx, src_idx)] = next(v for v in var_list if v.code == "foreign_prefix_variation")
        elif p.multi_first_count >= 2 and rng.random() < 0.6:
            assigned[(person_idx, src_idx)] = next(v for v in var_list if v.code == "compound_multi_name")
        else:
            assigned[(person_idx, src_idx)] = rng.choice(choices if choices else var_list)
            
    return assigned

# Транслитерация ГОСТ/BGN
_CYR_TO_LAT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
    'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
    'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts',
    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
}

def cyr_to_latin(text: str) -> str:
    return "".join(_CYR_TO_LAT.get(c, c) for c in text)

_RU_KEYBOARD = "йцукенгшщзхъфывапролджэячсмитьбю.ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,"
_EN_KEYBOARD = "qwertyuiop[]asdfghjkl;'zxcvbnm,./QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<?>"
_RU2EN = str.maketrans(_RU_KEYBOARD, _EN_KEYBOARD)

def render(variant: Variant, person: Person, rng) -> str:
    """Генерирует текстовое представление ФИО в соответствии с вариантом."""
    last, first, middle = person.last, person.first, person.middle or ""
    v = variant.code

    if v == "exact":
        return person.canonical

    if v == "reverse_order":
        # Имя Отчество Фамилия
        return f"{first} {middle} {last}".strip()

    if v == "first_last":
        # Имя Фамилия
        return f"{first} {last}".strip()

    if v == "last_first":
        # Фамилия Имя
        return f"{last} {first}".strip()

    if v == "initials_full":
        fi = first[0] + "."
        mi = (middle[0] + ".") if middle else ""
        return f"{last} {fi}{mi}".strip()

    if v == "initials_first_only":
        return f"{last} {first[0]}."

    if v == "initials_prefix":
        fi = first[0] + "."
        mi = (middle[0] + ".") if middle else ""
        return f"{fi}{mi} {last}".strip()

    if v == "honorific_title":
        titles = ["господин", "товарищ", "г-н", "Dr.", "профессор", "уважаемый", "сэр"]
        title = rng.choice(titles)
        order = rng.choice([
            f"{title} {last} {first}",
            f"{title} {first} {last}",
            f"{last} {first} {middle} ({title})"
        ])
        return order

    if v == "translit_en":
        # Английское написание
        # Заменяем популярные имена на их международный вид
        trans_name = first
        if "Георгий" in first or "Юрий" in first or "Егор" in first:
            trans_name = "George"
        elif "Александр" in first:
            trans_name = "Alexander"
        elif "Михаил" in first:
            trans_name = "Michael"
        elif "Иван" in first:
            trans_name = "John"
        else:
            trans_name = cyr_to_latin(first)

        trans_last = cyr_to_latin(last)
        return f"{trans_name} {trans_last}"

    if v == "etymology_cognate":
        # Подмена на однокоренное этимологическое имя
        alt_first = first
        if "Георгий" in first:
            alt_first = first.replace("Георгий", rng.choice(["Юрий", "Егор"]))
        elif "Юрий" in first:
            alt_first = first.replace("Юрий", rng.choice(["Георгий", "Егор"]))
        elif "Егор" in first:
            alt_first = first.replace("Егор", rng.choice(["Юрий", "Георгий"]))
        elif "Иван" in first:
            alt_first = first.replace("Иван", "Ян")
        elif "Оксана" in first:
            alt_first = first.replace("Оксана", "Ксения")
        elif "Ксения" in first:
            alt_first = first.replace("Ксения", "Оксана")
        elif "Елена" in first:
            alt_first = first.replace("Елена", "Алёна")
        return canonical_from_parts(last, alt_first, middle)

    if v == "foreign_prefix_variation":
        # Слитно или дефис или смена регистра приставки
        if " " in last:
            parts = last.split(" ")
            pfx = "".join(parts[:-1])
            surn = parts[-1]
            mod_last = rng.choice([
                f"{pfx.capitalize()}{surn}",       # VanBeethoven
                f"{pfx.lower()}-{surn}",          # van-beethoven
                f"{pfx.upper()} {surn}",          # VON DER Leyen
                f"{surn}, {pfx}"                  # Beethoven, van
            ])
            return f"{mod_last} {first}"
        return person.canonical

    if v == "compound_multi_name":
        # Замена дефиса на пробел или перестановка частей двойного имени
        if "-" in first:
            f_parts = first.split("-")
            f_mod = rng.choice([" ".join(f_parts), " ".join(reversed(f_parts))])
            return f"{last} {f_mod}"
        return f"{last} {first} {middle}"

    if v == "homoglyph_mixed":
        # Подмена кириллических букв на латинские
        res = []
        for c in person.canonical:
            if c in HOMOGLYPHS and rng.random() < 0.35:
                res.append(HOMOGLYPHS[c])
            else:
                res.append(c)
        return "".join(res)

    if v == "typo_levenshtein":
        # Случайная опечатка в фамилии
        if len(last) > 4:
            idx = rng.randint(2, len(last) - 2)
            # Транспозиция
            l_list = list(last)
            l_list[idx], l_list[idx+1] = l_list[idx+1], l_list[idx]
            mod_last = "".join(l_list)
            return canonical_from_parts(mod_last, first, middle)
        return person.canonical

    if v == "keyboard_layout":
        # Набор в неверной раскладке
        sample = f"{last} {first}"
        return sample.translate(_RU2EN)

    return person.canonical
