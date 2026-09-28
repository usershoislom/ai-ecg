"""
diagnostic_labels.py

Переводы названий 5 диагностических классов модели (NORM/MI/CD/HYP/STTC) для
отображения в /predict-ответах. НАМЕРЕННО статический словарь в коде, а не
чтение из БД (annotation_classes) - см. обсуждение: /predict должен оставаться
полностью stateless (без обращения к Postgres), это ядро клинической функции,
и оно не должно зависеть от доступности БД или от того, что врач сделал с
таксономией аннотаций (переименовал/деактивировал класс). Обученные классы
модели неизменны в рамках версии модели - им место в коде, а не в
редактируемой врачом таблице.

Содержимое совпадает с db/seed.py SUPERCLASSES по смыслу (тот же медицинский
термин), но это два независимых источника - при обновлении перевода здесь
поправить нужно ЗДЕСЬ, а не ждать, что где-то поменяется само.
"""

import json, os

_TRANSLATIONS_SUPERCLASS: dict[str, dict[str, str]] = {
    "NORM": {"ru": "Норма", "uz": "Norma"},
    "MI": {"ru": "Инфаркт миокарда", "uz": "Miokard infarkti"},
    "CD": {"ru": "Нарушения проводимости", "uz": "O'tkazuvchanlik buzilishi"},
    "HYP": {"ru": "Гипертрофия", "uz": "Gipertrofiya"},
    "STTC": {"ru": "Изменения ST/T", "uz": "ST/T o'zgarishlari"},
}


_TRANSLATIONS_SUBCLASS: dict[str, dict[str, str]] = {
    "NORM_ABNORMAL_ECG": {
        "en": "ABNORMAL ECG",
        "ru": "Аномальная ЭКГ",
        "uz": "Anormal EKG",
    },
    "NORM_NORMAL_SINUS_RHYTHM": {
        "en": "NORMAL SINUS RHYTHM",
        "ru": "Нормальный синусовый ритм",
        "uz": "Normal sinus ritmi",
    },
    "NORM_NORMAL_ECG": {"en": "NORMAL ECG", "ru": "Нормальная ЭКГ", "uz": "Normal EKG"},
    "OTHER_SINUS_RHYTHM": {
        "en": "SINUS RHYTHM",
        "ru": "Синусовый ритм",
        "uz": "Sinus ritmi",
    },
    "OTHER_SINUS_BRADYCARDIA": {
        "en": "SINUS BRADYCARDIA",
        "ru": "Синусовая брадикардия",
        "uz": "Sinus bradikardiyasi",
    },
    "OTHER_AF": {
        "en": "ATRIAL FIBRILLATION",
        "ru": "Фибрилляция предсердий",
        "uz": "Bo'lmachalar fibrillyatsiyasi",
    },
    "OTHER_SINUS_TACHYCARDIA": {
        "en": "SINUS TACHYCARDIA",
        "ru": "Синусовая тахикардия",
        "uz": "Sinus taxikardiyasi",
    },
    "OTHER_ABNORMAL_ECG": {
        "en": "otherwise normal ecg",
        "ru": "Аномальная ЭКГ",
        "uz": "Anormal EKG",
    },
    "OTHER_LEFT_AXIS_DEVIATION": {
        "en": "LEFT AXIS DEVIATION",
        "ru": "Отклонение электрической оси влево",
        "uz": "Elektr o'qining chapga og'ishi",
    },
    "OTHER_PVC": {
        "en": "PREMATURE VENTRICULAR COMPLEXES",
        "ru": "Желудочковые экстрасистолы",
        "uz": "Qorincha ekstrasistolalari",
    },
    "OTHER_BORDERLINE_ECG": {
        "en": "BORDERLINE ECG",
        "ru": "Пограничная ЭКГ",
        "uz": "Chegaraviy EKG",
    },
    "CD_RBBB": {
        "en": "RIGHT BUNDLE BRANCH BLOCK",
        "ru": "Блокада правой ножки пучка Гиса",
        "uz": "O'ng tutam oyoqchasi blokadasi",
    },
    "MI_SEPTAL": {
        "en": "SEPTAL INFARCT",
        "ru": "Септальный инфаркт миокарда",
        "uz": "Septal miokard infarkti",
    },
    "HYP_LAE": {
        "en": "LEFT ATRIAL ENLARGEMENT",
        "ru": "Увеличение левого предсердия",
        "uz": "Chap bo'lmacha kengayishi",
    },
    "STTC_NON_SPECIFIC_T_WAVE_ABNORMALITY": {
        "en": "NONSPECIFIC T WAVE ABNORMALITY",
        "ru": "Неспецифические изменения зубца T",
        "uz": "T tishchasining nospetsifik o'zgarishi",
    },
    "STTC_LOW_VOLTAGE_QRS": {
        "en": "LOW VOLTAGE QRS",
        "ru": "Низкий вольтаж комплекса QRS",
        "uz": "QRS kompleksining past voltaji",
    },
    "OTHER_PAC": {
        "en": "PREMATURE ATRIAL COMPLEXES",
        "ru": "Предсердные экстрасистолы",
        "uz": "Bo'lmacha ekstrasistolalari",
    },
    "MI_ANTERIOR": {
        "en": "ANTERIOR INFARCT",
        "ru": "Передний инфаркт миокарда",
        "uz": "Old devor miokard infarkti",
    },
    "CD_INCOMPLETE_RBBB": {
        "en": "INCOMPLETE RIGHT BUNDLE BRANCH BLOCK",
        "ru": "Неполная блокада правой ножки пучка Гиса",
        "uz": "O'ng tutam oyoqchasining to'liq bo'lmagan blokadasi",
    },
    "OTHER_PREMATURE_SUPRAVENTRICULAR_COMPLEXES": {
        "en": "PREMATURE SUPRAVENTRICULAR COMPLEXES",
        "ru": "Преждевременные наджелудочковые комплексы",
        "uz": "Muddatidan oldingi supraventrikulyar komplekslar",
    },
    "CD_LBBB": {
        "en": "LEFT BUNDLE BRANCH BLOCK",
        "ru": "Блокада левой ножки пучка Гиса",
        "uz": "Chap tutam oyoqchasi blokadasi",
    },
    "STTC_T_WAVE_ABNORMALITY_NOW_EVIDENT": {
        "en": "NONSPECIFIC T WAVE ABNORMALITY NOW EVIDENT IN",
        "ru": "Вновь выявленная неспецифическая аномалия зубца T",
        "uz": "T tishchasining yangi aniqlangan nospetsifik o'zgarishi",
    },
    "STTC_T_WAVE_ABNORMALITY_NO_LONGER_EVIDENT": {
        "en": "NONSPECIFIC T WAVE ABNORMALITY NO LONGER EVIDENT IN",
        "ru": "Ранее выявленная неспецифическая аномалия зубца T больше не определяется",
        "uz": "Avval aniqlangan T tishchasining nospetsifik o'zgarishi endi aniqlanmaydi",
    },
    "STTC_T_INVERSION_NOW_EVIDENT": {
        "en": "T WAVE INVERSION NOW EVIDENT IN",
        "ru": "Вновь выявленная инверсия зубца T",
        "uz": "T tishchasi inversiyasining yangi aniqlanishi",
    },
    "MI_LATERAL": {
        "en": "LATERAL INFARCT",
        "ru": "Боковой инфаркт миокарда",
        "uz": "Yon devor miokard infarkti",
    },
    "STTC_NON_SPECIFIC_ST_ABNORMALITY": {
        "en": "NONSPECIFIC ST ABNORMALITY",
        "ru": "Неспецифические изменения сегмента ST",
        "uz": "ST segmentining nospetsifik o'zgarishi",
    },
    "HYP_LVH": {
        "en": "LEFT VENTRICULAR HYPERTROPHY",
        "ru": "Гипертрофия левого желудочка",
        "uz": "Chap qorincha gipertrofiyasi",
    },
    "STTC_T_INVERSION_NO_LONGER_EVIDENT": {
        "en": "T WAVE INVERSION NO LONGER EVIDENT IN",
        "ru": "Инверсия зубца T больше не определяется",
        "uz": "T tishchasi inversiyasi endi aniqlanmaydi",
    },
    "OTHER_RAPID_VENTRICULAR_RESPONSE": {
        "en": "WITH RAPID VENTRICULAR RESPONSE",
        "ru": "Быстрый желудочковый ответ",
        "uz": "Tezkor qorincha javobi",
    },
    "STTC_QT_SHORTENED": {
        "en": "QT HAS SHORTENED",
        "ru": "Укорочение интервала QT",
        "uz": "QT intervalining qisqarishi",
    },
    "STTC_QT_LENGTHENED": {
        "en": "QT HAS LENGTHENED",
        "ru": "Удлинение интервала QT",
        "uz": "QT intervalining uzayishi",
    },
    "OTHER_FUSION_COMPLEXES": {
        "en": "FUSION COMPLEXES",
        "ru": "Сливные комплексы",
        "uz": "Fuzion komplekslar",
    },
    "OTHER_ATRIAL_FLUTTER": {
        "en": "ATRIAL FLUTTER",
        "ru": "Трепетание предсердий",
        "uz": "Bo'lmachalar flutteri",
    },
    "OTHER_MARKED_SINUS_BRADYCARDIA": {
        "en": "MARKED SINUS BRADYCARDIA",
        "ru": "Выраженная синусовая брадикардия",
        "uz": "Yaqqol sinus bradikardiyasi",
    },
    "OTHER_SINUS_ARRHYTHMIA": {
        "en": "WITH SINUS ARRHYTHMIA",
        "ru": "Синусовая аритмия",
        "uz": "Sinus aritmiyasi",
    },
    "STTC_NON_SPECIFIC_ST_T_ABNORMALITY": {
        "en": "NONSPECIFIC ST AND T WAVE ABNORMALITY",
        "ru": "Неспецифические изменения ST и зубца T",
        "uz": "ST va T tishchasining nospetsifik o'zgarishi",
    },
    "CD_LAFB": {
        "en": "LEFT ANTERIOR FASCICULAR BLOCK",
        "ru": "Блокада передней ветви левой ножки пучка Гиса",
        "uz": "Gis tutami chap oyoqchasining oldingi shoxi blokadasi",
    },
    "OTHER_RIGHT_AXIS_DEVIATION": {
        "en": "RIGHT AXIS DEVIATION",
        "ru": "Отклонение электрической оси вправо",
        "uz": "Elektr o'qining o'ngga og'ishi",
    },
    "OTHER_ECTOPIC_ATRIAL_RHYTHM": {
        "en": "ECTOPIC ATRIAL RHYTHM",
        "ru": "Эктопический предсердный ритм",
        "uz": "Ektopik bo'lmacha ritmi",
    },
    "OTHER_UNDETERMINED_RHYTHM": {
        "en": "UNDETERMINED RHYTHM",
        "ru": "Ритм не определён",
        "uz": "Ritm aniqlanmagan",
    },
    "MI_ANTEROSEPTAL": {
        "en": "ANTEROSEPTAL INFARCT",
        "ru": "Переднеперегородочный инфаркт миокарда",
        "uz": "Oldingi-septal miokard infarkti",
    },
    "OTHER_RIGHTWARD_AXIS": {
        "en": "RIGHTWARD AXIS",
        "ru": "Правое направление электрической оси",
        "uz": "Elektr o'qining o'ngga yo'nalishi",
    },
    "OTHER_SHORT_PR": {
        "en": "WITH SHORT PR",
        "ru": "Укороченный интервал PR",
        "uz": "PR intervalining qisqarishi",
    },
    "OTHER_MARKED_SINUS_ARRHYTHMIA": {
        "en": "WITH MARKED SINUS ARRHYTHMIA",
        "ru": "Выраженная синусовая аритмия",
        "uz": "Yaqqol sinus aritmiyasi",
    },
    "STTC_ST_NO_LONGER_DEPRESSED": {
        "en": "ST NO LONGER DEPRESSED IN",
        "ru": "Депрессия ST больше не определяется",
        "uz": "ST depressiyasi endi aniqlanmaydi",
    },
    "STTC_INVERTED_T_REPLACED_NON_SPECIFIC_T": {
        "en": "INVERTED T WAVES HAVE REPLACED NONSPECIFIC T WAVE ABNORMALITY IN",
        "ru": "Инвертированные зубцы T заменили неспецифические изменения T",
        "uz": "Inversiyalangan T tishchalari nospetsifik T o'zgarishlarini almashtirdi",
    },
    "STTC_NON_SPECIFIC_ST_SEGMENT_CHANGE": {
        "en": "NON-SPECIFIC CHANGE IN ST SEGMENT IN",
        "ru": "Неспецифические изменения сегмента ST",
        "uz": "ST segmentining nospetsifik o'zgarishi",
    },
    "STTC_NON_SPECIFIC_T_REPLACED_INVERTED_T": {
        "en": "NONSPECIFIC T WAVE ABNORMALITY HAS REPLACED INVERTED T WAVES IN",
        "ru": "Неспецифические изменения T заменили инверсию T",
        "uz": "T ning nospetsifik o'zgarishlari inversiyalangan T ni almashtirdi",
    },
    "OTHER_JUNCTIONAL_RHYTHM": {
        "en": "JUNCTIONAL RHYTHM",
        "ru": "Атриовентрикулярный узловой ритм",
        "uz": "AV tugun ritmi",
    },
    "OTHER_ELECTRONIC_ATRIAL_PACEMAKER": {
        "en": "ELECTRONIC ATRIAL PACEMAKER",
        "ru": "Электронный предсердный электрокардиостимулятор",
        "uz": "Elektron bo'lmacha kardiostimulyatori",
    },
    "OTHER_ABERRANT_CONDUCTION": {
        "en": "ABERRANT CONDUCTION",
        "ru": "Аберрантное проведение",
        "uz": "Aberrant o'tkazilish",
    },
    "OTHER_ELECTRONIC_VENTRICULAR_PACEMAKER": {
        "en": "ELECTRONIC VENTRICULAR PACEMAKER",
        "ru": "Электронный желудочковый электрокардиостимулятор",
        "uz": "Elektron qorincha kardiostimulyatori",
    },
    "STTC_T_INVERSION_LESS_EVIDENT": {
        "en": "T WAVE INVERSION LESS EVIDENT IN",
        "ru": "Менее выраженная инверсия зубца T",
        "uz": "T tishchasi inversiyasining kamroq ifodalanganligi",
    },
    "MI_ANTEROLATERAL": {
        "en": "ANTEROLATERAL INFARCT",
        "ru": "Переднебоковой инфаркт миокарда",
        "uz": "Oldingi-yon devor miokard infarkti",
    },
    "STTC_REPOLARIZATION_ABNORMALITY": {
        "en": "WITH REPOLARIZATION ABNORMALITY",
        "ru": "Нарушение реполяризации",
        "uz": "Repolyarizatsiya buzilishi",
    },
    "CD_RSR_V1_DELAY": {
        "en": "RSR' OR QR PATTERN IN V1 SUGGESTS RIGHT VENTRICULAR CONDUCTION DELAY",
        "ru": "Паттерн RSR' или QR в V1, предполагающий задержку внутрижелудочкового проведения справа",
        "uz": "V1 da RSR' yoki QR patterni, o'ng qorincha o'tkazilishining kechikishini ko'rsatadi",
    },
    "STTC_T_INVERSION_MORE_EVIDENT": {
        "en": "T WAVE INVERSION MORE EVIDENT IN",
        "ru": "Более выраженная инверсия зубца T",
        "uz": "T tishchasi inversiyasining yanada ifodalanganligi",
    },
    "OTHER_WIDE_QRS_RHYTHM": {
        "en": "WIDE QRS RHYTHM",
        "ru": "Ритм с широкими комплексами QRS",
        "uz": "Keng QRS kompleksli ritm",
    },
    "OTHER_PVC_OR_ABERRANT_CONDUCTED_COMPLEXES": {
        "en": "WITH PREMATURE VENTRICULAR OR ABERRANTLY CONDUCTED COMPLEXES",
        "ru": "Желудочковые экстрасистолы или аберрантно проведённые комплексы",
        "uz": "Qorincha ekstrasistolalari yoki aberrant o'tkazilgan komplekslar",
    },
    "HYP_RAE": {
        "en": "RIGHT ATRIAL ENLARGEMENT",
        "ru": "Увеличение правого предсердия",
        "uz": "O'ng bo'lmacha kengayishi",
    },
    "MI_INFERIOR": {
        "en": "INFERIOR INFARCT",
        "ru": "Нижний инфаркт миокарда",
        "uz": "Pastki devor miokard infarkti",
    },
    "CD_INCOMPLETE_LBBB": {
        "en": "INCOMPLETE LEFT BUNDLE BRANCH BLOCK",
        "ru": "Неполная блокада левой ножки пучка Гиса",
        "uz": "Chap tutam oyoqchasining to'liq bo'lmagan blokadasi",
    },
    "HYP_LVH_VOLTAGE_CRITERIA": {
        "en": "VOLTAGE CRITERIA FOR LEFT VENTRICULAR HYPERTROPHY",
        "ru": "Вольтажные критерии гипертрофии левого желудочка",
        "uz": "Chap qorincha gipertrofiyasining voltaj mezonlari",
    },
    "OTHER_DIGITALIS_EFFECT": {
        "en": "OR DIGITALIS EFFECT",
        "ru": "Эффект дигиталиса",
        "uz": "Digitalis ta'siri",
    },
    "CD_BIFASCICULAR_BLOCK": {
        "en": "BIFASCICULAR BLOCK",
        "ru": "Бифасцикулярная блокада",
        "uz": "Bifassikulyar blokada",
    },
    "STTC_ST_NO_LONGER_ELEVATED": {
        "en": "ST NO LONGER ELEVATED IN",
        "ru": "Элевация ST больше не определяется",
        "uz": "ST elevatsiyasi endi aniqlanmaydi",
    },
    "OTHER_SLOW_VENTRICULAR_RESPONSE": {
        "en": "WITH SLOW VENTRICULAR RESPONSE",
        "ru": "Медленный желудочковый ответ",
        "uz": "Sekin qorincha javobi",
    },
    "STTC_ST_ELEVATION_NOW_PRESENT": {
        "en": "ST ELEVATION NOW PRESENT IN",
        "ru": "Вновь выявленная элевация ST",
        "uz": "ST elevatsiyasining yangi aniqlanishi",
    },
    "OTHER_PREMATURE_ECTOPIC_COMPLEXES": {
        "en": "PREMATURE ECTOPIC COMPLEXES",
        "ru": "Преждевременные эктопические комплексы",
        "uz": "Muddatidan oldingi ektopik komplekslar",
    },
    "CD_LPFB": {
        "en": "LEFT POSTERIOR FASCICULAR BLOCK",
        "ru": "Блокада задней ветви левой ножки пучка Гиса",
        "uz": "Gis tutami chap oyoqchasining orqa shoxi blokadasi",
    },
    "STTC_T_WAVE_AMPLITUDE_DECREASED": {
        "en": "T WAVE AMPLITUDE HAS DECREASED IN",
        "ru": "Снижение амплитуды зубца T",
        "uz": "T tishchasi amplitudasining kamayishi",
    },
    "OTHER_COMPETING_JUNCTIONAL_PACEMAKER": {
        "en": "WITH A COMPETING JUNCTIONAL PACEMAKER",
        "ru": "Конкурирующий узловой водитель ритма",
        "uz": "Raqobat qiluvchi AV tugun stimulyatori",
    },
    "OTHER_RIGHT_SUPERIOR_AXIS_DEVIATION": {
        "en": "RIGHT SUPERIOR AXIS DEVIATION",
        "ru": "Отклонение электрической оси вправо и вверх",
        "uz": "Elektr o'qining o'ngga va yuqoriga og'ishi",
    },
    "HYP_BIATRIAL_ENLARGEMENT": {
        "en": "BIATRIAL ENLARGEMENT",
        "ru": "Увеличение обоих предсердий",
        "uz": "Ikkala bo'lmacha kengayishi",
    },
    "OTHER_VENTRICULAR_PACED_RHYTHM": {
        "en": "VENTRICULAR-PACED RHYTHM",
        "ru": "Желудочковый стимулируемый ритм",
        "uz": "Qorincha stimulyatsiyalangan ritmi",
    },
    "OTHER_ATRIAL_PACED_RHYTHM": {
        "en": "ATRIAL-PACED RHYTHM",
        "ru": "Предсердно-стимулируемый ритм",
        "uz": "Bo'lmacha stimulyatsiyalangan ritmi",
    },
    "STTC_T_WAVE_AMPLITUDE_INCREASED": {
        "en": "T WAVE AMPLITUDE HAS INCREASED IN",
        "ru": "Увеличение амплитуды зубца T",
        "uz": "T tishchasi amplitudasining oshishi",
    },
    "CD_QRS_WIDENING": {
        "en": "WITH QRS WIDENING",
        "ru": "Расширение комплекса QRS",
        "uz": "QRS kompleksining kengayishi",
    },
    "CD_AV_BLOCK_1": {
        "en": "WITH 1ST DEGREE AV BLOCK",
        "ru": "АВ-блокада I степени",
        "uz": "AB blokada I daraja",
    },
    "STTC_PROLONGED_QT": {
        "en": "PROLONGED QT",
        "ru": "Удлинённый интервал QT",
        "uz": "Uzaygan QT intervali",
    },
    "CD_PROLONGED_AV_CONDUCTION": {
        "en": "WITH PROLONGED AV CONDUCTION",
        "ru": "Замедленное АВ-проведение",
        "uz": "AV o'tkazilishining uzayishi",
    },
    "HYP_RVH": {
        "en": "RIGHT VENTRICULAR HYPERTROPHY",
        "ru": "Гипертрофия правого желудочка",
        "uz": "O'ng qorincha gipertrofiyasi",
    },
    "STTC_QRS_WIDENING_REPOLARIZATION_ABNORMALITY": {
        "en": "WITH QRS WIDENING AND REPOLARIZATION ABNORMALITY",
        "ru": "Расширение QRS с нарушением реполяризации",
        "uz": "QRS kengayishi va repoliarizatsiya buzilishi",
    },
    "OTHER_ATRIAL_SENSED_VENTRICULAR_PACED_RHYTHM": {
        "en": "ATRIAL-SENSED VENTRICULAR-PACED RHYTHM",
        "ru": "Предсердно-чувствуемый желудочково-стимулируемый ритм",
        "uz": "Bo'lmacha sezuvchi, qorincha stimulyatsiyalangan ritm",
    },
    "OTHER_AV_SEQUENTIAL_DUAL_CHAMBER_PACEMAKER": {
        "en": "AV SEQUENTIAL OR DUAL CHAMBER ELECTRONIC PACEMAKER",
        "ru": "Электронный двухкамерный АВ-последовательный электрокардиостимулятор",
        "uz": "Elektron ikki kamerali AV ketma-ket kardiostimulyatori",
    },
    "OTHER_PULMONARY_DISEASE_PATTERN": {
        "en": "PULMONARY DISEASE PATTERN",
        "ru": "ЭКГ-паттерн при лёгочном заболевании",
        "uz": "O'pka kasalligiga xos EKG patterni",
    },
    "MI_ACUTE_STEMI": {
        "en": "ACUTE MI / STEMI",
        "ru": "Острый инфаркт миокарда / STEMI",
        "uz": "O'tkir miokard infarkti / STEMI",
    },
    "MI_INFERIOR_POSTERIOR": {
        "en": "INFERIOR-POSTERIOR INFARCT",
        "ru": "Нижнезадний инфаркт миокарда",
        "uz": "Pastki-orqa devor miokard infarkti",
    },
    "CD_NONSPECIFIC_IVCD": {
        "en": "NONSPECIFIC INTRAVENTRICULAR CONDUCTION DELAY",
        "ru": "Неспецифическое нарушение внутрижелудочковой проводимости",
        "uz": "Qorincha ichki o'tkazilishining nospetsifik buzilishi",
    },
    "OTHER_PVC_AND_FUSION_COMPLEXES": {
        "en": "PREMATURE VENTRICULAR AND FUSION COMPLEXES",
        "ru": "Желудочковые экстрасистолы и сливные комплексы",
        "uz": "Qorincha ekstrasistolalari va fuzion komplekslar",
    },
    "OTHER_BIGEMINY": {
        "en": "IN A PATTERN OF BIGEMINY",
        "ru": "Бигеминия",
        "uz": "Bigeminiya",
    },
    "OTHER_AV_DUAL_PACED_RHYTHM": {
        "en": "AV DUAL-PACED RHYTHM",
        "ru": "Двухкамерный АВ-стимулируемый ритм",
        "uz": "Ikki kamerali AV stimulyatsiyalangan ritm",
    },
    "OTHER_SUPRAVENTRICULAR_TACHYCARDIA": {
        "en": "SUPRAVENTRICULAR TACHYCARDIA",
        "ru": "Наджелудочковая тахикардия",
        "uz": "Supraventrikulyar taxikardiya",
    },
    "OTHER_VENTRICULAR_PACED_COMPLEXES": {
        "en": "VENTRICULAR-PACED COMPLEXES",
        "ru": "Желудочковые стимулируемые комплексы",
        "uz": "Qorincha stimulyatsiyalangan komplekslari",
    },
    "OTHER_WIDE_QRS_TACHYCARDIA": {
        "en": "WIDE QRS TACHYCARDIA",
        "ru": "Тахикардия с широким комплексом QRS",
        "uz": "Keng QRS kompleksli taxikardiya",
    },
    "CD_RSR_V1": {
        "en": "RSR' PATTERN IN V1",
        "ru": "Паттерн RSR' в V1",
        "uz": "V1 da RSR' patterni",
    },
    "STTC_ST_LESS_DEPRESSED": {
        "en": "ST LESS DEPRESSED IN",
        "ru": "Менее выраженная депрессия ST",
        "uz": "ST depressiyasining kamayishi",
    },
    "OTHER_VENTRICULAR_TACHYCARDIA": {
        "en": "VENTRICULAR TACHYCARDIA",
        "ru": "Желудочковая тахикардия",
        "uz": "Qorincha taxikardiyasi",
    },
    "STTC_EARLY_REPOLARIZATION": {
        "en": "EARLY REPOLARIZATION",
        "ru": "Ранняя реполяризация",
        "uz": "Erta repoliarizatsiya",
    },
    "STTC_ST_MORE_DEPRESSED": {
        "en": "ST MORE DEPRESSED IN",
        "ru": "Более выраженная депрессия ST",
        "uz": "ST depressiyasining kuchayishi",
    },
    "STTC_ANTEROLATERAL_LEADS": {
        "en": "ANTEROLATERAL LEADS",
        "ru": "Изменения в переднебоковых отведениях",
        "uz": "Oldingi-yon o'zaklarda o'zgarishlar",
    },
    "OTHER_ELECTRONIC_DEMAND_PACING": {
        "en": "ELECTRONIC DEMAND PACING",
        "ru": "Электронная стимуляция по требованию",
        "uz": "Talab bo'yicha elektron stimulyatsiya",
    },
    "CD_RBBB_LAFB": {
        "en": "RBBB AND LEFT ANTERIOR FASCICULAR BLOCK",
        "ru": "Блокада правой ножки и передней ветви левой ножки пучка Гиса",
        "uz": "O'ng tutam oyoqchasi va chap tutam oldingi shoxi blokadasi",
    },
    "MI_LATERAL_INJURY": {
        "en": "LATERAL INJURY PATTERN",
        "ru": "Боковой паттерн повреждения миокарда",
        "uz": "Yon devor miokard shikastlanishi patterni",
    },
    "OTHER_BIVENTRICULAR_PACEMAKER": {
        "en": "BIVENTRICULAR PACEMAKER DETECTED",
        "ru": "Выявлен бивентрикулярный электрокардиостимулятор",
        "uz": "Biventrikulyar kardiostimulyator aniqlangan",
    },
    "OTHER_PACEMAKER_FAILURE": {
        "en": "SUSPECT UNSPECIFIED PACEMAKER FAILURE",
        "ru": "Подозрение на неисправность электрокардиостимулятора",
        "uz": "Kardiostimulyator nosozligiga shubha",
    },
    "OTHER_WPW": {
        "en": "WOLFF-PARKINSON-WHITE",
        "ru": "Синдром Вольфа–Паркинсона–Уайта",
        "uz": "Volf–Parkinson–White sindromi",
    },
    "OTHER_VENTRICULAR_ESCAPE_COMPLEXES": {
        "en": "WITH VENTRICULAR ESCAPE COMPLEXES",
        "ru": "Желудочковые комплексы замещения",
        "uz": "Qorincha o'rnini bosuvchi komplekslar",
    },
    "MI_INFERIOR_INJURY": {
        "en": "INFERIOR INJURY PATTERN",
        "ru": "Нижний паттерн повреждения миокарда",
        "uz": "Pastki devor miokard shikastlanishi patterni",
    },
    "MI_INFERIOR_RV_INVOLVEMENT": {
        "en": "CONSIDER RIGHT VENTRICULAR INVOLVEMENT IN ACUTE INFERIOR INFARCT",
        "ru": "Подозрение на вовлечение правого желудочка при остром нижнем инфаркте",
        "uz": "O'tkir pastki infarktda o'ng qorincha ishtirokiga shubha",
    },
    "STTC_ST_ELEVATION_REPLACED_DEPRESSION": {
        "en": "ST ELEVATION HAS REPLACED ST DEPRESSION IN",
        "ru": "Элевация ST сменила депрессию ST",
        "uz": "ST elevatsiyasi ST depressiyasini almashtirdi",
    },
    "CD_NONSPECIFIC_IV_BLOCK": {
        "en": "NONSPECIFIC INTRAVENTRICULAR BLOCK",
        "ru": "Неспецифическая внутрижелудочковая блокада",
        "uz": "Qorincha ichki nospetsifik blokadasi",
    },
    "OTHER_MASKED_BY_FASCICULAR_BLOCK": {
        "en": "MASKED BY FASCICULAR BLOCK",
        "ru": "Скрыто фасцикулярной блокадой",
        "uz": "Fassikulyar blokada bilan niqoblangan",
    },
    "OTHER_PEDIATRIC_ECG_ANALYSIS": {
        "en": "PEDIATRIC ECG ANALYSIS",
        "ru": "Педиатрическая интерпретация ЭКГ",
        "uz": "Pediatrik EKG tahlili",
    },
    "OTHER_BLOCKED": {"en": "BLOCKED", "ru": "Блокированная форма", "uz": "Bloklangan"},
    "OTHER_UNDETERMINED_RHYTHM_IRREGULARITY": {
        "en": "WITH UNDETERMINED RHYTHM IRREGULARITY",
        "ru": "Нерегулярность ритма не определена",
        "uz": "Ritm notekisligi aniqlanmagan",
    },
    "OTHER_LEFTWARD_AXIS": {
        "en": "LEFTWARD AXIS",
        "ru": "Левое направление электрической оси",
        "uz": "Elektr o'qining chapga yo'nalishi",
    },
    "OTHER_SECOND_DEGREE_SA_BLOCK_MOBITZ_I": {
        "en": "WITH 2ND DEGREE SA BLOCK MOBITZ I",
        "ru": "Синоатриальная блокада II степени типа Мобитц I",
        "uz": "II darajali sinoatrial blokada, Mobitz I turi",
    },
    "OTHER_ACUTE": {"en": "ACUTE", "ru": "Острое состояние", "uz": "O'tkir holat"},
    "OTHER_ABNORMAL_LEFT_AXIS_DEVIATION": {
        "en": "ABNORMAL LEFT AXIS DEVIATION",
        "ru": "Аномальное отклонение электрической оси влево",
        "uz": "Elektr o'qining anormal chapga og'ishi",
    },
    "CD_COMPLETE_HEART_BLOCK": {
        "en": "WITH COMPLETE HEART BLOCK",
        "ru": "Полная АВ-блокада",
        "uz": "To'liq AV blokada",
    },
    "OTHER_NO_P_WAVES": {
        "en": "NO P-WAVES FOUND",
        "ru": "Зубцы P не выявляются",
        "uz": "P tishchalari aniqlanmaydi",
    },
    "STTC_ST_LESS_ELEVATED": {
        "en": "ST LESS ELEVATED IN",
        "ru": "Менее выраженная элевация ST",
        "uz": "ST elevatsiyasining kamayishi",
    },
    "OTHER_RETROGRADE_CONDUCTION": {
        "en": "WITH RETROGRADE CONDUCTION",
        "ru": "Ретроградное проведение",
        "uz": "Retrograd o'tkazilish",
    },
    "STTC_ST_MORE_ELEVATED": {
        "en": "ST MORE ELEVATED IN",
        "ru": "Более выраженная элевация ST",
        "uz": "ST elevatsiyasining kuchayishi",
    },
    "OTHER_JUNCTIONAL_BRADYCARDIA": {
        "en": "JUNCTIONAL BRADYCARDIA",
        "ru": "Узловая брадикардия",
        "uz": "AV tugun bradikardiyasi",
    },
    "OTHER_VARIABLE_AV_BLOCK": {
        "en": "WITH VARIABLE AV BLOCK",
        "ru": "АВ-блокада с переменным проведением",
        "uz": "O'zgaruvchan o'tkazilishli AV blokada",
    },
    "MI_ANTERIOR_INJURY": {
        "en": "ANTERIOR INJURY PATTERN",
        "ru": "Передний паттерн повреждения миокарда",
        "uz": "Old devor miokard shikastlanishi patterni",
    },
    "OTHER_JUNCTIONAL_ESCAPE_COMPLEXES": {
        "en": "WITH JUNCTIONAL ESCAPE COMPLEXES",
        "ru": "Узловые комплексы замещения",
        "uz": "AV tugun o'rnini bosuvchi komplekslar",
    },
    "MI_ACUTE": {
        "en": "ACUTE MI",
        "ru": "Острый инфаркт миокарда",
        "uz": "O'tkir miokard infarkti",
    },
    "OTHER_ACUTE_PERICARDITIS": {
        "en": "ACUTE PERICARDITIS",
        "ru": "Острый перикардит",
        "uz": "O'tkir perikardit",
    },
    "MI_POSTERIOR": {
        "en": "POSTERIOR INFARCT",
        "ru": "Задний инфаркт миокарда",
        "uz": "Orqa devor miokard infarkti",
    },
    "OTHER_IDIOVENTRICULAR_RHYTHM": {
        "en": "IDIOVENTRICULAR RHYTHM",
        "ru": "Идиовентрикулярный ритм",
        "uz": "Idioventrikulyar ritm",
    },
    "OTHER_SECOND_DEGREE_SA_BLOCK_MOBITZ_II": {
        "en": "WITH 2ND DEGREE SA BLOCK MOBITZ II",
        "ru": "Синоатриальная блокада II степени типа Мобитц II",
        "uz": "II darajali sinoatrial blokada, Mobitz II turi",
    },
    "OTHER_R_IN_AVL": {
        "en": "R IN AVL",
        "ru": "Зубец R в отведении aVL",
        "uz": "aVL o'qida R tishchasi",
    },
    "OTHER_SINUS_ATRIAL_CAPTURE": {
        "en": "SINUS/ATRIAL CAPTURE",
        "ru": "Захват синусовым/предсердным импульсом",
        "uz": "Sinus/bo'lmacha impulsi bilan capture",
    },
    "OTHER_AV_DUAL_PACED_COMPLEXES": {
        "en": "AV DUAL-PACED COMPLEXES",
        "ru": "Двухкамерные АВ-стимулируемые комплексы",
        "uz": "Ikki kamerali AV stimulyatsiyalangan komplekslar",
    },
    "MI_INFEROLATERAL_INJURY": {
        "en": "INFEROLATERAL INJURY PATTERN",
        "ru": "Нижнебоковой паттерн повреждения миокарда",
        "uz": "Pastki-yon devor miokard shikastlanishi patterni",
    },
    "CD_RBBB_LPFB": {
        "en": "RBBB AND LEFT POSTERIOR FASCICULAR BLOCK",
        "ru": "Блокада правой ножки и задней ветви левой ножки пучка Гиса",
        "uz": "O'ng tutam oyoqchasi va chap tutam orqa shoxi blokadasi",
    },
    "MI_ANTEROLATERAL_INJURY": {
        "en": "ANTEROLATERAL INJURY PATTERN",
        "ru": "Переднебоковой паттерн повреждения миокарда",
        "uz": "Oldingi-yon devor miokard shikastlanishi patterni",
    },
    "OTHER_ATRIAL_PACED_COMPLEXES": {
        "en": "ATRIAL-PACED COMPLEXES",
        "ru": "Предсердно-стимулируемые комплексы",
        "uz": "Bo'lmacha stimulyatsiyalangan komplekslar",
    },
    "OTHER_SINUS_PAUSE": {
        "en": "WITH SINUS PAUSE",
        "ru": "Синусовая пауза",
        "uz": "Sinus pauzasi",
    },
    "HYP_BIVENTRICULAR": {
        "en": "BIVENTRICULAR HYPERTROPHY",
        "ru": "Бивентрикулярная гипертрофия",
        "uz": "Biventrikulyar gipertrofiya",
    },
    "OTHER_ABNORMAL_RIGHT_AXIS_DEVIATION": {
        "en": "ABNORMAL RIGHT AXIS DEVIATION",
        "ru": "Аномальное отклонение электрической оси вправо",
        "uz": "Elektr o'qining anormal o'ngga og'ishi",
    },
    "OTHER_SUPRAVENTRICULAR_COMPLEXES": {
        "en": "SUPRAVENTRICULAR COMPLEXES",
        "ru": "Наджелудочковые комплексы",
        "uz": "Supraventrikulyar komplekslar",
    },
    "OTHER_SECOND_DEGREE_AV_BLOCK_MOBITZ_I": {
        "en": "WITH 2ND DEGREE AV BLOCK MOBITZ I",
        "ru": "АВ-блокада II степени типа Мобитц I",
        "uz": "II darajali AV blokada, Mobitz I turi",
    },
    "CD_AV_2_TO_1": {
        "en": "WITH 2:1 AV CONDUCTION",
        "ru": "АВ-проведение 2:1",
        "uz": "2:1 AV o'tkazilish",
    },
    "OTHER_AV_DISSOCIATION": {
        "en": "WITH AV DISSOCIATION",
        "ru": "АВ-диссоциация",
        "uz": "AV dissotsiatsiyasi",
    },
    "OTHER_MULTIFOCAL_ATRIAL_TACHYCARDIA": {
        "en": "MULTIFOCAL ATRIAL TACHYCARDIA",
        "ru": "Многоочаговая предсердная тахикардия",
        "uz": "Ko'p o'choqli bo'lmacha taxikardiyasi",
    },
}

_DEFAULT_LANG = "ru"


def translate_label_all(code: str) -> dict[str, str]:
    entry = _TRANSLATIONS_SUPERCLASS.get(code, {})
    return {"ru": entry.get("ru", code), "uz": entry.get("uz", code)}


def translate_label(code: str, lang: str = _DEFAULT_LANG) -> str:
    """
    Переведённое название класса. Фолбэк: запрошенный язык -> ru -> сам код
    (для неизвестных/будущих кодов модели, которых ещё нет в словаре - лучше
    показать код, чем упасть с ошибкой).
    """
    entry = _TRANSLATIONS_SUPERCLASS.get(code)
    if entry is None:
        return code
    return entry.get(lang) or entry.get(_DEFAULT_LANG) or code


_TRANSLATIONS_RAW150: dict[str, dict[str, str]] = {
    item["en"]: {"ru": item["ru"], "uz": item["uz"]}
    for item in _TRANSLATIONS_SUBCLASS.values()
}

# чтобы работало, даже если модель отдаёт другой регистр
_TRANSLATIONS_RAW150_UPPER: dict[str, dict[str, str]] = {
    key.upper(): value for key, value in _TRANSLATIONS_RAW150.items()
}


def translate_label_all_raw150(label: str) -> dict[str, str]:
    key = label.strip()

    translated = _TRANSLATIONS_RAW150.get(key)
    if translated is None:
        translated = _TRANSLATIONS_RAW150_UPPER.get(key.upper())

    if translated is None:
        return {"ru": label, "uz": label}

    return translated
