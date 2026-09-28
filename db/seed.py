"""
seed.py

Дефолтные классы - 5 суперклассов из ТЗ + OTHER, и несколько примеров
подклассов под каждым (для старта; реальный список подклассов команда
скорее всего расширит через POST /annotation/classes или отдельным
уточнением - структура это уже поддерживает).

Идемпотентно: повторный запуск не создаёт дублей (проверка по code).
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AnnotationClass, ClassType

logger = logging.getLogger(__name__)

SUPERCLASSES = [
    ("NORM", {"ru": "Норма", "uz": "Norma"}),
    ("MI", {"ru": "Инфаркт миокарда", "uz": "Miokard infarkti"}),
    ("CD", {"ru": "Нарушения проводимости", "uz": "O'tkazuvchanlik buzilishi"}),
    ("HYP", {"ru": "Гипертрофия", "uz": "Gipertrofiya"}),
    ("STTC", {"ru": "Изменения ST/T", "uz": "ST/T o'zgarishlari"}),
    ("OTHER", {"ru": "Другое", "uz": "Boshqa"}),
]

# (код_суперкласса, код_подкласса, {переводы})
SUBCLASSES = [
    ("NORM", "NORM_ABNORMAL_ECG", {"ru": "Аномальная ЭКГ", "uz": "Anormal EKG"}),
    (
        "NORM",
        "NORM_NORMAL_SINUS_RHYTHM",
        {"ru": "Нормальный синусовый ритм", "uz": "Normal sinus ritmi"},
    ),
    ("NORM", "NORM_NORMAL_ECG", {"ru": "Нормальная ЭКГ", "uz": "Normal EKG"}),
    ("OTHER", "OTHER_SINUS_RHYTHM", {"ru": "Синусовый ритм", "uz": "Sinus ritmi"}),
    (
        "OTHER",
        "OTHER_SINUS_BRADYCARDIA",
        {"ru": "Синусовая брадикардия", "uz": "Sinus bradikardiyasi"},
    ),
    (
        "OTHER",
        "OTHER_AF",
        {"ru": "Фибрилляция предсердий", "uz": "Bo'lmachalar fibrillyatsiyasi"},
    ),
    (
        "OTHER",
        "OTHER_SINUS_TACHYCARDIA",
        {"ru": "Синусовая тахикардия", "uz": "Sinus taxikardiyasi"},
    ),
    ("OTHER", "OTHER_ABNORMAL_ECG", {"ru": "Аномальная ЭКГ", "uz": "Anormal EKG"}),
    (
        "OTHER",
        "OTHER_LEFT_AXIS_DEVIATION",
        {
            "ru": "Отклонение электрической оси влево",
            "uz": "Elektr o'qining chapga og'ishi",
        },
    ),
    (
        "OTHER",
        "OTHER_PVC",
        {"ru": "Желудочковые экстрасистолы", "uz": "Qorincha ekstrasistolalari"},
    ),
    (
        "OTHER",
        "OTHER_BORDERLINE_ECG",
        {"ru": "Пограничная ЭКГ", "uz": "Chegaraviy EKG"},
    ),
    (
        "CD",
        "CD_RBBB",
        {
            "ru": "Блокада правой ножки пучка Гиса",
            "uz": "O'ng tutam oyoqchasi blokadasi",
        },
    ),
    (
        "MI",
        "MI_SEPTAL",
        {"ru": "Септальный инфаркт миокарда", "uz": "Septal miokard infarkti"},
    ),
    (
        "HYP",
        "HYP_LAE",
        {"ru": "Увеличение левого предсердия", "uz": "Chap bo'lmacha kengayishi"},
    ),
    (
        "STTC",
        "STTC_NON_SPECIFIC_T_WAVE_ABNORMALITY",
        {
            "ru": "Неспецифические изменения зубца T",
            "uz": "T tishchasining nospetsifik o'zgarishi",
        },
    ),
    (
        "STTC",
        "STTC_LOW_VOLTAGE_QRS",
        {"ru": "Низкий вольтаж комплекса QRS", "uz": "QRS kompleksining past voltaji"},
    ),
    (
        "OTHER",
        "OTHER_PAC",
        {"ru": "Предсердные экстрасистолы", "uz": "Bo'lmacha ekstrasistolalari"},
    ),
    (
        "MI",
        "MI_ANTERIOR",
        {"ru": "Передний инфаркт миокарда", "uz": "Old devor miokard infarkti"},
    ),
    (
        "CD",
        "CD_INCOMPLETE_RBBB",
        {
            "ru": "Неполная блокада правой ножки пучка Гиса",
            "uz": "O'ng tutam oyoqchasining to'liq bo'lmagan blokadasi",
        },
    ),
    (
        "OTHER",
        "OTHER_PREMATURE_SUPRAVENTRICULAR_COMPLEXES",
        {
            "ru": "Преждевременные наджелудочковые комплексы",
            "uz": "Muddatidan oldingi supraventrikulyar komplekslar",
        },
    ),
    (
        "CD",
        "CD_LBBB",
        {
            "ru": "Блокада левой ножки пучка Гиса",
            "uz": "Chap tutam oyoqchasi blokadasi",
        },
    ),
    (
        "STTC",
        "STTC_T_WAVE_ABNORMALITY_NOW_EVIDENT",
        {
            "ru": "Вновь выявленная неспецифическая аномалия зубца T",
            "uz": "T tishchasining yangi aniqlangan nospetsifik o'zgarishi",
        },
    ),
    (
        "STTC",
        "STTC_T_WAVE_ABNORMALITY_NO_LONGER_EVIDENT",
        {
            "ru": "Ранее выявленная неспецифическая аномалия зубца T больше не определяется",
            "uz": "Avval aniqlangan T tishchasining nospetsifik o'zgarishi endi aniqlanmaydi",
        },
    ),
    (
        "STTC",
        "STTC_T_INVERSION_NOW_EVIDENT",
        {
            "ru": "Вновь выявленная инверсия зубца T",
            "uz": "T tishchasi inversiyasining yangi aniqlanishi",
        },
    ),
    (
        "MI",
        "MI_LATERAL",
        {"ru": "Боковой инфаркт миокарда", "uz": "Yon devor miokard infarkti"},
    ),
    (
        "STTC",
        "STTC_NON_SPECIFIC_ST_ABNORMALITY",
        {
            "ru": "Неспецифические изменения сегмента ST",
            "uz": "ST segmentining nospetsifik o'zgarishi",
        },
    ),
    (
        "HYP",
        "HYP_LVH",
        {"ru": "Гипертрофия левого желудочка", "uz": "Chap qorincha gipertrofiyasi"},
    ),
    (
        "STTC",
        "STTC_T_INVERSION_NO_LONGER_EVIDENT",
        {
            "ru": "Инверсия зубца T больше не определяется",
            "uz": "T tishchasi inversiyasi endi aniqlanmaydi",
        },
    ),
    (
        "OTHER",
        "OTHER_RAPID_VENTRICULAR_RESPONSE",
        {"ru": "Быстрый желудочковый ответ", "uz": "Tezkor qorincha javobi"},
    ),
    (
        "STTC",
        "STTC_QT_SHORTENED",
        {"ru": "Укорочение интервала QT", "uz": "QT intervalining qisqarishi"},
    ),
    (
        "STTC",
        "STTC_QT_LENGTHENED",
        {"ru": "Удлинение интервала QT", "uz": "QT intervalining uzayishi"},
    ),
    (
        "OTHER",
        "OTHER_FUSION_COMPLEXES",
        {"ru": "Сливные комплексы", "uz": "Fuzion komplekslar"},
    ),
    (
        "OTHER",
        "OTHER_ATRIAL_FLUTTER",
        {"ru": "Трепетание предсердий", "uz": "Bo'lmachalar flutteri"},
    ),
    (
        "OTHER",
        "OTHER_MARKED_SINUS_BRADYCARDIA",
        {"ru": "Выраженная синусовая брадикардия", "uz": "Yaqqol sinus bradikardiyasi"},
    ),
    (
        "OTHER",
        "OTHER_SINUS_ARRHYTHMIA",
        {"ru": "Синусовая аритмия", "uz": "Sinus aritmiyasi"},
    ),
    (
        "STTC",
        "STTC_NON_SPECIFIC_ST_T_ABNORMALITY",
        {
            "ru": "Неспецифические изменения ST и зубца T",
            "uz": "ST va T tishchasining nospetsifik o'zgarishi",
        },
    ),
    (
        "CD",
        "CD_LAFB",
        {
            "ru": "Блокада передней ветви левой ножки пучка Гиса",
            "uz": "Gis tutami chap oyoqchasining oldingi shoxi blokadasi",
        },
    ),
    (
        "OTHER",
        "OTHER_RIGHT_AXIS_DEVIATION",
        {
            "ru": "Отклонение электрической оси вправо",
            "uz": "Elektr o'qining o'ngga og'ishi",
        },
    ),
    (
        "OTHER",
        "OTHER_ECTOPIC_ATRIAL_RHYTHM",
        {"ru": "Эктопический предсердный ритм", "uz": "Ektopik bo'lmacha ritmi"},
    ),
    (
        "OTHER",
        "OTHER_UNDETERMINED_RHYTHM",
        {"ru": "Ритм не определён", "uz": "Ritm aniqlanmagan"},
    ),
    (
        "MI",
        "MI_ANTEROSEPTAL",
        {
            "ru": "Переднеперегородочный инфаркт миокарда",
            "uz": "Oldingi-septal miokard infarkti",
        },
    ),
    (
        "OTHER",
        "OTHER_RIGHTWARD_AXIS",
        {
            "ru": "Правое направление электрической оси",
            "uz": "Elektr o'qining o'ngga yo'nalishi",
        },
    ),
    (
        "OTHER",
        "OTHER_SHORT_PR",
        {"ru": "Укороченный интервал PR", "uz": "PR intervalining qisqarishi"},
    ),
    (
        "OTHER",
        "OTHER_MARKED_SINUS_ARRHYTHMIA",
        {"ru": "Выраженная синусовая аритмия", "uz": "Yaqqol sinus aritmiyasi"},
    ),
    (
        "STTC",
        "STTC_ST_NO_LONGER_DEPRESSED",
        {
            "ru": "Депрессия ST больше не определяется",
            "uz": "ST depressiyasi endi aniqlanmaydi",
        },
    ),
    (
        "STTC",
        "STTC_INVERTED_T_REPLACED_NON_SPECIFIC_T",
        {
            "ru": "Инвертированные зубцы T заменили неспецифические изменения T",
            "uz": "Inversiyalangan T tishchalari nospetsifik T o'zgarishlarini almashtirdi",
        },
    ),
    (
        "STTC",
        "STTC_NON_SPECIFIC_ST_SEGMENT_CHANGE",
        {
            "ru": "Неспецифические изменения сегмента ST",
            "uz": "ST segmentining nospetsifik o'zgarishi",
        },
    ),
    (
        "STTC",
        "STTC_NON_SPECIFIC_T_REPLACED_INVERTED_T",
        {
            "ru": "Неспецифические изменения T заменили инверсию T",
            "uz": "T ning nospetsifik o'zgarishlari inversiyalangan T ni almashtirdi",
        },
    ),
    (
        "OTHER",
        "OTHER_JUNCTIONAL_RHYTHM",
        {"ru": "Атриовентрикулярный узловой ритм", "uz": "AV tugun ritmi"},
    ),
    (
        "OTHER",
        "OTHER_ELECTRONIC_ATRIAL_PACEMAKER",
        {
            "ru": "Электронный предсердный электрокардиостимулятор",
            "uz": "Elektron bo'lmacha kardiostimulyatori",
        },
    ),
    (
        "OTHER",
        "OTHER_ABERRANT_CONDUCTION",
        {"ru": "Аберрантное проведение", "uz": "Aberrant o'tkazilish"},
    ),
    (
        "OTHER",
        "OTHER_ELECTRONIC_VENTRICULAR_PACEMAKER",
        {
            "ru": "Электронный желудочковый электрокардиостимулятор",
            "uz": "Elektron qorincha kardiostimulyatori",
        },
    ),
    (
        "STTC",
        "STTC_T_INVERSION_LESS_EVIDENT",
        {
            "ru": "Менее выраженная инверсия зубца T",
            "uz": "T tishchasi inversiyasining kamroq ifodalanganligi",
        },
    ),
    (
        "MI",
        "MI_ANTEROLATERAL",
        {
            "ru": "Переднебоковой инфаркт миокарда",
            "uz": "Oldingi-yon devor miokard infarkti",
        },
    ),
    (
        "STTC",
        "STTC_REPOLARIZATION_ABNORMALITY",
        {"ru": "Нарушение реполяризации", "uz": "Repolyarizatsiya buzilishi"},
    ),
    (
        "CD",
        "CD_RSR_V1_DELAY",
        {
            "ru": "Паттерн RSR' или QR в V1, предполагающий задержку внутрижелудочкового проведения справа",
            "uz": "V1 da RSR' yoki QR patterni, o'ng qorincha o'tkazilishining kechikishini ko'rsatadi",
        },
    ),
    (
        "STTC",
        "STTC_T_INVERSION_MORE_EVIDENT",
        {
            "ru": "Более выраженная инверсия зубца T",
            "uz": "T tishchasi inversiyasining yanada ifodalanganligi",
        },
    ),
    (
        "OTHER",
        "OTHER_WIDE_QRS_RHYTHM",
        {"ru": "Ритм с широкими комплексами QRS", "uz": "Keng QRS kompleksli ritm"},
    ),
    (
        "OTHER",
        "OTHER_PVC_OR_ABERRANT_CONDUCTED_COMPLEXES",
        {
            "ru": "Желудочковые экстрасистолы или аберрантно проведённые комплексы",
            "uz": "Qorincha ekstrasistolalari yoki aberrant o'tkazilgan komplekslar",
        },
    ),
    (
        "HYP",
        "HYP_RAE",
        {"ru": "Увеличение правого предсердия", "uz": "O'ng bo'lmacha kengayishi"},
    ),
    (
        "MI",
        "MI_INFERIOR",
        {"ru": "Нижний инфаркт миокарда", "uz": "Pastki devor miokard infarkti"},
    ),
    (
        "CD",
        "CD_INCOMPLETE_LBBB",
        {
            "ru": "Неполная блокада левой ножки пучка Гиса",
            "uz": "Chap tutam oyoqchasining to'liq bo'lmagan blokadasi",
        },
    ),
    (
        "HYP",
        "HYP_LVH_VOLTAGE_CRITERIA",
        {
            "ru": "Вольтажные критерии гипертрофии левого желудочка",
            "uz": "Chap qorincha gipertrofiyasining voltaj mezonlari",
        },
    ),
    (
        "OTHER",
        "OTHER_DIGITALIS_EFFECT",
        {"ru": "Эффект дигиталиса", "uz": "Digitalis ta'siri"},
    ),
    (
        "CD",
        "CD_BIFASCICULAR_BLOCK",
        {"ru": "Бифасцикулярная блокада", "uz": "Bifassikulyar blokada"},
    ),
    (
        "STTC",
        "STTC_ST_NO_LONGER_ELEVATED",
        {
            "ru": "Элевация ST больше не определяется",
            "uz": "ST elevatsiyasi endi aniqlanmaydi",
        },
    ),
    (
        "OTHER",
        "OTHER_SLOW_VENTRICULAR_RESPONSE",
        {"ru": "Медленный желудочковый ответ", "uz": "Sekin qorincha javobi"},
    ),
    (
        "STTC",
        "STTC_ST_ELEVATION_NOW_PRESENT",
        {
            "ru": "Вновь выявленная элевация ST",
            "uz": "ST elevatsiyasining yangi aniqlanishi",
        },
    ),
    (
        "OTHER",
        "OTHER_PREMATURE_ECTOPIC_COMPLEXES",
        {
            "ru": "Преждевременные эктопические комплексы",
            "uz": "Muddatidan oldingi ektopik komplekslar",
        },
    ),
    (
        "CD",
        "CD_LPFB",
        {
            "ru": "Блокада задней ветви левой ножки пучка Гиса",
            "uz": "Gis tutami chap oyoqchasining orqa shoxi blokadasi",
        },
    ),
    (
        "STTC",
        "STTC_T_WAVE_AMPLITUDE_DECREASED",
        {
            "ru": "Снижение амплитуды зубца T",
            "uz": "T tishchasi amplitudasining kamayishi",
        },
    ),
    (
        "OTHER",
        "OTHER_COMPETING_JUNCTIONAL_PACEMAKER",
        {
            "ru": "Конкурирующий узловой водитель ритма",
            "uz": "Raqobat qiluvchi AV tugun stimulyatori",
        },
    ),
    (
        "OTHER",
        "OTHER_RIGHT_SUPERIOR_AXIS_DEVIATION",
        {
            "ru": "Отклонение электрической оси вправо и вверх",
            "uz": "Elektr o'qining o'ngga va yuqoriga og'ishi",
        },
    ),
    (
        "HYP",
        "HYP_BIATRIAL_ENLARGEMENT",
        {"ru": "Увеличение обоих предсердий", "uz": "Ikkala bo'lmacha kengayishi"},
    ),
    (
        "OTHER",
        "OTHER_VENTRICULAR_PACED_RHYTHM",
        {
            "ru": "Желудочковый стимулируемый ритм",
            "uz": "Qorincha stimulyatsiyalangan ritmi",
        },
    ),
    (
        "OTHER",
        "OTHER_ATRIAL_PACED_RHYTHM",
        {
            "ru": "Предсердно-стимулируемый ритм",
            "uz": "Bo'lmacha stimulyatsiyalangan ritmi",
        },
    ),
    (
        "STTC",
        "STTC_T_WAVE_AMPLITUDE_INCREASED",
        {
            "ru": "Увеличение амплитуды зубца T",
            "uz": "T tishchasi amplitudasining oshishi",
        },
    ),
    (
        "CD",
        "CD_QRS_WIDENING",
        {"ru": "Расширение комплекса QRS", "uz": "QRS kompleksining kengayishi"},
    ),
    (
        "CD",
        "CD_AV_BLOCK_1",
        {"ru": "АВ-блокада I степени", "uz": "AB blokada I daraja"},
    ),
    (
        "STTC",
        "STTC_PROLONGED_QT",
        {"ru": "Удлинённый интервал QT", "uz": "Uzaygan QT intervali"},
    ),
    (
        "CD",
        "CD_PROLONGED_AV_CONDUCTION",
        {"ru": "Замедленное АВ-проведение", "uz": "AV o'tkazilishining uzayishi"},
    ),
    (
        "HYP",
        "HYP_RVH",
        {"ru": "Гипертрофия правого желудочка", "uz": "O'ng qorincha gipertrofiyasi"},
    ),
    (
        "STTC",
        "STTC_QRS_WIDENING_REPOLARIZATION_ABNORMALITY",
        {
            "ru": "Расширение QRS с нарушением реполяризации",
            "uz": "QRS kengayishi va repoliarizatsiya buzilishi",
        },
    ),
    (
        "OTHER",
        "OTHER_ATRIAL_SENSED_VENTRICULAR_PACED_RHYTHM",
        {
            "ru": "Предсердно-чувствуемый желудочково-стимулируемый ритм",
            "uz": "Bo'lmacha sezuvchi, qorincha stimulyatsiyalangan ritm",
        },
    ),
    (
        "OTHER",
        "OTHER_AV_SEQUENTIAL_DUAL_CHAMBER_PACEMAKER",
        {
            "ru": "Электронный двухкамерный АВ-последовательный электрокардиостимулятор",
            "uz": "Elektron ikki kamerali AV ketma-ket kardiostimulyatori",
        },
    ),
    (
        "OTHER",
        "OTHER_PULMONARY_DISEASE_PATTERN",
        {
            "ru": "ЭКГ-паттерн при лёгочном заболевании",
            "uz": "O'pka kasalligiga xos EKG patterni",
        },
    ),
    (
        "MI",
        "MI_ACUTE_STEMI",
        {
            "ru": "Острый инфаркт миокарда / STEMI",
            "uz": "O'tkir miokard infarkti / STEMI",
        },
    ),
    (
        "MI",
        "MI_INFERIOR_POSTERIOR",
        {
            "ru": "Нижнезадний инфаркт миокарда",
            "uz": "Pastki-orqa devor miokard infarkti",
        },
    ),
    (
        "CD",
        "CD_NONSPECIFIC_IVCD",
        {
            "ru": "Неспецифическое нарушение внутрижелудочковой проводимости",
            "uz": "Qorincha ichki o'tkazilishining nospetsifik buzilishi",
        },
    ),
    (
        "OTHER",
        "OTHER_PVC_AND_FUSION_COMPLEXES",
        {
            "ru": "Желудочковые экстрасистолы и сливные комплексы",
            "uz": "Qorincha ekstrasistolalari va fuzion komplekslar",
        },
    ),
    ("OTHER", "OTHER_BIGEMINY", {"ru": "Бигеминия", "uz": "Bigeminiya"}),
    (
        "OTHER",
        "OTHER_AV_DUAL_PACED_RHYTHM",
        {
            "ru": "Двухкамерный АВ-стимулируемый ритм",
            "uz": "Ikki kamerali AV stimulyatsiyalangan ritm",
        },
    ),
    (
        "OTHER",
        "OTHER_SUPRAVENTRICULAR_TACHYCARDIA",
        {"ru": "Наджелудочковая тахикардия", "uz": "Supraventrikulyar taxikardiya"},
    ),
    (
        "OTHER",
        "OTHER_VENTRICULAR_PACED_COMPLEXES",
        {
            "ru": "Желудочковые стимулируемые комплексы",
            "uz": "Qorincha stimulyatsiyalangan komplekslari",
        },
    ),
    (
        "OTHER",
        "OTHER_WIDE_QRS_TACHYCARDIA",
        {
            "ru": "Тахикардия с широким комплексом QRS",
            "uz": "Keng QRS kompleksli taxikardiya",
        },
    ),
    ("CD", "CD_RSR_V1", {"ru": "Паттерн RSR' в V1", "uz": "V1 da RSR' patterni"}),
    (
        "STTC",
        "STTC_ST_LESS_DEPRESSED",
        {"ru": "Менее выраженная депрессия ST", "uz": "ST depressiyasining kamayishi"},
    ),
    (
        "OTHER",
        "OTHER_VENTRICULAR_TACHYCARDIA",
        {"ru": "Желудочковая тахикардия", "uz": "Qorincha taxikardiyasi"},
    ),
    (
        "STTC",
        "STTC_EARLY_REPOLARIZATION",
        {"ru": "Ранняя реполяризация", "uz": "Erta repoliarizatsiya"},
    ),
    (
        "STTC",
        "STTC_ST_MORE_DEPRESSED",
        {"ru": "Более выраженная депрессия ST", "uz": "ST depressiyasining kuchayishi"},
    ),
    (
        "STTC",
        "STTC_ANTEROLATERAL_LEADS",
        {
            "ru": "Изменения в переднебоковых отведениях",
            "uz": "Oldingi-yon o'zaklarda o'zgarishlar",
        },
    ),
    (
        "OTHER",
        "OTHER_ELECTRONIC_DEMAND_PACING",
        {
            "ru": "Электронная стимуляция по требованию",
            "uz": "Talab bo'yicha elektron stimulyatsiya",
        },
    ),
    (
        "CD",
        "CD_RBBB_LAFB",
        {
            "ru": "Блокада правой ножки и передней ветви левой ножки пучка Гиса",
            "uz": "O'ng tutam oyoqchasi va chap tutam oldingi shoxi blokadasi",
        },
    ),
    (
        "MI",
        "MI_LATERAL_INJURY",
        {
            "ru": "Боковой паттерн повреждения миокарда",
            "uz": "Yon devor miokard shikastlanishi patterni",
        },
    ),
    (
        "OTHER",
        "OTHER_BIVENTRICULAR_PACEMAKER",
        {
            "ru": "Выявлен бивентрикулярный электрокардиостимулятор",
            "uz": "Biventrikulyar kardiostimulyator aniqlangan",
        },
    ),
    (
        "OTHER",
        "OTHER_PACEMAKER_FAILURE",
        {
            "ru": "Подозрение на неисправность электрокардиостимулятора",
            "uz": "Kardiostimulyator nosozligiga shubha",
        },
    ),
    (
        "OTHER",
        "OTHER_WPW",
        {
            "ru": "Синдром Вольфа–Паркинсона–Уайта",
            "uz": "Volf–Parkinson–White sindromi",
        },
    ),
    (
        "OTHER",
        "OTHER_VENTRICULAR_ESCAPE_COMPLEXES",
        {
            "ru": "Желудочковые комплексы замещения",
            "uz": "Qorincha o'rnini bosuvchi komplekslar",
        },
    ),
    (
        "MI",
        "MI_INFERIOR_INJURY",
        {
            "ru": "Нижний паттерн повреждения миокарда",
            "uz": "Pastki devor miokard shikastlanishi patterni",
        },
    ),
    (
        "MI",
        "MI_INFERIOR_RV_INVOLVEMENT",
        {
            "ru": "Подозрение на вовлечение правого желудочка при остром нижнем инфаркте",
            "uz": "O'tkir pastki infarktda o'ng qorincha ishtirokiga shubha",
        },
    ),
    (
        "STTC",
        "STTC_ST_ELEVATION_REPLACED_DEPRESSION",
        {
            "ru": "Элевация ST сменила депрессию ST",
            "uz": "ST elevatsiyasi ST depressiyasini almashtirdi",
        },
    ),
    (
        "CD",
        "CD_NONSPECIFIC_IV_BLOCK",
        {
            "ru": "Неспецифическая внутрижелудочковая блокада",
            "uz": "Qorincha ichki nospetsifik blokadasi",
        },
    ),
    (
        "OTHER",
        "OTHER_MASKED_BY_FASCICULAR_BLOCK",
        {
            "ru": "Скрыто фасцикулярной блокадой",
            "uz": "Fassikulyar blokada bilan niqoblangan",
        },
    ),
    (
        "OTHER",
        "OTHER_PEDIATRIC_ECG_ANALYSIS",
        {"ru": "Педиатрическая интерпретация ЭКГ", "uz": "Pediatrik EKG tahlili"},
    ),
    ("OTHER", "OTHER_BLOCKED", {"ru": "Блокированная форма", "uz": "Bloklangan"}),
    (
        "OTHER",
        "OTHER_UNDETERMINED_RHYTHM_IRREGULARITY",
        {
            "ru": "Нерегулярность ритма не определена",
            "uz": "Ritm notekisligi aniqlanmagan",
        },
    ),
    (
        "OTHER",
        "OTHER_LEFTWARD_AXIS",
        {
            "ru": "Левое направление электрической оси",
            "uz": "Elektr o'qining chapga yo'nalishi",
        },
    ),
    (
        "OTHER",
        "OTHER_SECOND_DEGREE_SA_BLOCK_MOBITZ_I",
        {
            "ru": "Синоатриальная блокада II степени типа Мобитц I",
            "uz": "II darajali sinoatrial blokada, Mobitz I turi",
        },
    ),
    ("OTHER", "OTHER_ACUTE", {"ru": "Острое состояние", "uz": "O'tkir holat"}),
    (
        "OTHER",
        "OTHER_ABNORMAL_LEFT_AXIS_DEVIATION",
        {
            "ru": "Аномальное отклонение электрической оси влево",
            "uz": "Elektr o'qining anormal chapga og'ishi",
        },
    ),
    (
        "CD",
        "CD_COMPLETE_HEART_BLOCK",
        {"ru": "Полная АВ-блокада", "uz": "To'liq AV blokada"},
    ),
    (
        "OTHER",
        "OTHER_NO_P_WAVES",
        {"ru": "Зубцы P не выявляются", "uz": "P tishchalari aniqlanmaydi"},
    ),
    (
        "STTC",
        "STTC_ST_LESS_ELEVATED",
        {"ru": "Менее выраженная элевация ST", "uz": "ST elevatsiyasining kamayishi"},
    ),
    (
        "OTHER",
        "OTHER_RETROGRADE_CONDUCTION",
        {"ru": "Ретроградное проведение", "uz": "Retrograd o'tkazilish"},
    ),
    (
        "STTC",
        "STTC_ST_MORE_ELEVATED",
        {"ru": "Более выраженная элевация ST", "uz": "ST elevatsiyasining kuchayishi"},
    ),
    (
        "OTHER",
        "OTHER_JUNCTIONAL_BRADYCARDIA",
        {"ru": "Узловая брадикардия", "uz": "AV tugun bradikardiyasi"},
    ),
    (
        "OTHER",
        "OTHER_VARIABLE_AV_BLOCK",
        {
            "ru": "АВ-блокада с переменным проведением",
            "uz": "O'zgaruvchan o'tkazilishli AV blokada",
        },
    ),
    (
        "MI",
        "MI_ANTERIOR_INJURY",
        {
            "ru": "Передний паттерн повреждения миокарда",
            "uz": "Old devor miokard shikastlanishi patterni",
        },
    ),
    (
        "OTHER",
        "OTHER_JUNCTIONAL_ESCAPE_COMPLEXES",
        {
            "ru": "Узловые комплексы замещения",
            "uz": "AV tugun o'rnini bosuvchi komplekslar",
        },
    ),
    (
        "MI",
        "MI_ACUTE",
        {"ru": "Острый инфаркт миокарда", "uz": "O'tkir miokard infarkti"},
    ),
    (
        "OTHER",
        "OTHER_ACUTE_PERICARDITIS",
        {"ru": "Острый перикардит", "uz": "O'tkir perikardit"},
    ),
    (
        "MI",
        "MI_POSTERIOR",
        {"ru": "Задний инфаркт миокарда", "uz": "Orqa devor miokard infarkti"},
    ),
    (
        "OTHER",
        "OTHER_IDIOVENTRICULAR_RHYTHM",
        {"ru": "Идиовентрикулярный ритм", "uz": "Idioventrikulyar ritm"},
    ),
    (
        "OTHER",
        "OTHER_SECOND_DEGREE_SA_BLOCK_MOBITZ_II",
        {
            "ru": "Синоатриальная блокада II степени типа Мобитц II",
            "uz": "II darajali sinoatrial blokada, Mobitz II turi",
        },
    ),
    (
        "OTHER",
        "OTHER_R_IN_AVL",
        {"ru": "Зубец R в отведении aVL", "uz": "aVL o'qida R tishchasi"},
    ),
    (
        "OTHER",
        "OTHER_SINUS_ATRIAL_CAPTURE",
        {
            "ru": "Захват синусовым/предсердным импульсом",
            "uz": "Sinus/bo'lmacha impulsi bilan capture",
        },
    ),
    (
        "OTHER",
        "OTHER_AV_DUAL_PACED_COMPLEXES",
        {
            "ru": "Двухкамерные АВ-стимулируемые комплексы",
            "uz": "Ikki kamerali AV stimulyatsiyalangan komplekslar",
        },
    ),
    (
        "MI",
        "MI_INFEROLATERAL_INJURY",
        {
            "ru": "Нижнебоковой паттерн повреждения миокарда",
            "uz": "Pastki-yon devor miokard shikastlanishi patterni",
        },
    ),
    (
        "CD",
        "CD_RBBB_LPFB",
        {
            "ru": "Блокада правой ножки и задней ветви левой ножки пучка Гиса",
            "uz": "O'ng tutam oyoqchasi va chap tutam orqa shoxi blokadasi",
        },
    ),
    (
        "MI",
        "MI_ANTEROLATERAL_INJURY",
        {
            "ru": "Переднебоковой паттерн повреждения миокарда",
            "uz": "Oldingi-yon devor miokard shikastlanishi patterni",
        },
    ),
    (
        "OTHER",
        "OTHER_ATRIAL_PACED_COMPLEXES",
        {
            "ru": "Предсердно-стимулируемые комплексы",
            "uz": "Bo'lmacha stimulyatsiyalangan komplekslar",
        },
    ),
    ("OTHER", "OTHER_SINUS_PAUSE", {"ru": "Синусовая пауза", "uz": "Sinus pauzasi"}),
    (
        "HYP",
        "HYP_BIVENTRICULAR",
        {"ru": "Бивентрикулярная гипертрофия", "uz": "Biventrikulyar gipertrofiya"},
    ),
    (
        "OTHER",
        "OTHER_ABNORMAL_RIGHT_AXIS_DEVIATION",
        {
            "ru": "Аномальное отклонение электрической оси вправо",
            "uz": "Elektr o'qining anormal o'ngga og'ishi",
        },
    ),
    (
        "OTHER",
        "OTHER_SUPRAVENTRICULAR_COMPLEXES",
        {"ru": "Наджелудочковые комплексы", "uz": "Supraventrikulyar komplekslar"},
    ),
    (
        "OTHER",
        "OTHER_SECOND_DEGREE_AV_BLOCK_MOBITZ_I",
        {
            "ru": "АВ-блокада II степени типа Мобитц I",
            "uz": "II darajali AV blokada, Mobitz I turi",
        },
    ),
    ("CD", "CD_AV_2_TO_1", {"ru": "АВ-проведение 2:1", "uz": "2:1 AV o'tkazilish"}),
    (
        "OTHER",
        "OTHER_AV_DISSOCIATION",
        {"ru": "АВ-диссоциация", "uz": "AV dissotsiatsiyasi"},
    ),
    (
        "OTHER",
        "OTHER_MULTIFOCAL_ATRIAL_TACHYCARDIA",
        {
            "ru": "Многоочаговая предсердная тахикардия",
            "uz": "Ko'p o'choqli bo'lmacha taxikardiyasi",
        },
    ),
]


async def seed_default_classes(db: AsyncSession) -> None:
    existing = (await db.execute(select(AnnotationClass.code))).scalars().all()
    existing = set(existing)

    code_to_id = {}

    for code, names in SUPERCLASSES:
        if code in existing:
            row = (
                await db.execute(
                    select(AnnotationClass).where(AnnotationClass.code == code)
                )
            ).scalar_one()
            code_to_id[code] = row.id
            continue
        obj = AnnotationClass(
            type=ClassType.superclass, code=code, names=names, is_custom=False
        )
        db.add(obj)
        await db.flush()
        code_to_id[code] = obj.id

    for parent_code, code, names in SUBCLASSES:
        if code in existing:
            continue
        obj = AnnotationClass(
            type=ClassType.subclass,
            code=code,
            names=names,
            parent_class_id=code_to_id[parent_code],
            is_custom=False,
        )
        db.add(obj)

    await db.commit()
    logger.info(
        "Дефолтные классы аннотаций проверены/добавлены (%d суперклассов, %d подклассов)",
        len(SUPERCLASSES),
        len(SUBCLASSES),
    )
