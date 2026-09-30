# Корпус для проверки скрипта

Реальные русские тексты, на которых проверяется `check.py`. Файлы из `stop-slop-ru/evals/files/` для этого не годятся: их писала модель, и писала нарочно как карикатуры.

Сами тексты лежат в `corpus/texts/human/` и `corpus/texts/machine/` и в git не идут: они чужие. Здесь только список источников, чтобы корпус можно было собрать заново, и последние цифры.

## Правила отбора

- **Человеческий текст** опубликован до ноября 2022 года, то есть до ChatGPT. Дата проверяема: на странице или по снимку веб-архива.
- **Машинный текст** признан машинным кем-то снаружи: разметкой датасета или признанием автора. Своё суждение «похоже на ИИ» основанием не считается.
- Текст скачан дословно, curl и разбор HTML. WebFetch не годится, он пересказывает.
- От 800 до 5000 знаков, при длинном источнике берётся сплошной кусок.
- Файл начинается с комментария: `<!-- source: URL | published: дата | domain: профиль | label: human|machine | provenance: ... | excerpt: yes|no -->`. Из него скрипт прогона берёт профиль и метку.

## Прогон

```
python tools/run_corpus.py
python tools/run_corpus.py --old 799de77
```

Второй вариант ставит рядом версию из коммита.

## Результат на 2026-09-30

Сначала машинных текстов было 11, все из датасетов. Потом добавились 24 сырых ответа Sonnet 5.5, Opus 5.5 и Fable 5.1 на брифы из [briefs.md](briefs.md), файлы `g_*`.

| Версия | Живые (21) | Машинные из датасетов (11) | Все машинные (35) |
|--------|------------|----------------------------|-------------------|
| `799de77`, до правок | нет 12, слабые 3, сильные 6 | нет 5, слабые 1, сильные 5 | нет 26, слабые 1, сильные 8 |
| `63a60fd` | нет 17, слабые 4, сильные 0 | нет 7, слабые 2, сильные 2 | нет 30, слабые 2, сильные 3 |
| с обёрткой ответа | нет 17, слабые 4, сильные 0 | нет 7, слабые 2, сильные 2 | нет 9, слабые 14, сильные 12 |

Живые тексты скрипт больше не называет машиной. Машинные тексты из датасетов он почти не видит: медиана плотности у живых 1,6, у машинных 1,7. Каталог ловит грубые признаки вроде «Конечно!» и эмодзи, а научные аннотации GPT-4 и статьи GigaChat и YandexGPT написаны без них. Три из пяти машинных текстов старая версия поймала случайно, на ошибке с «в конечном итоге».

Модели 2026 года по лексике чистые. Их выдаёт обёртка ответа: вступление «Вот вариант…», предложение доработать, признание в домысле. Правила обёртки подобраны на тех же 24 текстах, так что цифра в последней строке завышена. Если человек скопировал только сам текст, без обёртки, скрипт его почти не видит.

Слабые места корпуса. Четыре машинных текста из датасетов это короткие научные аннотации. Пример из Википедии склеен из шести фрагментов. У 24 новых текстов восемь общих тем. Живых текстов в жанрах лендинга, документации API и делового письма нет.

Файлы `writer/before_*` и `writer/after_*` это выход `write-ru` до и после коммита `60a7649` на тех же брифах, с журналами прогона. Скрипт у обеих версий даёт «следов нет».

## Контрольный набор

Папка `texts/holdout/`. На этих текстах правила не подбирались, они проверяют, что правила работают на новых данных.

- `hg_*`: 24 сырых ответа Sonnet 5.5, Opus 5.5 и Fable 5.1 на брифы из [briefs-holdout.md](briefs-holdout.md). Темы другие, чем в `briefs.md`. В половине брифов просьба «только текст».
- `hh_*`: 16 живых текстов до ноября 2022 года в жанрах, которых не хватало: лендинги, «О нас», деловые письма, документация API, региональные новости.

| Группа | Следов нет | Слабые | Сильные |
|--------|------------|--------|---------|
| hg, брифы без запрета комментариев (12) | 1 | 9 | 2 |
| hg, «только текст» (12) | 10 | 2 | 0 |
| hh, живые (16) | 14 | 2 | 0 |

Обёртку ответа правила ловят и на новых темах: 11 из 12, пропущена аннотация Opus, которую он написал вовсе без обёртки. Без обёртки скрипт почти слеп: 2 из 12.

**Профиль вёрстки проверен и не принят.** Шесть признаков: жирный от одного раза на тысячу знаков, тире от 1,5, буква «ё», средняя фраза до 14 слов, абзацы из одной фразы от 40%, нет скобок. На обучающих текстах правило «4 из 6» отметило 19 из 24 машинных и 1 из 21 живого. На контрольных 15 из 24 машинных и 3 из 16 живых («О нас» и документация: короткие фразы и абзацы там норма жанра). Каждый шестой живой текст с ложной находкой это слишком много, в каталог профиль не вошёл.

### Источники контрольного набора

| Файл | Метка | Профиль | Дата | Источник | Как проверена дата |
|------|-------|---------|------|----------|--------------------|
| hh_about_brenda | human | full | 2020-07-15 | https://web.archive.org/web/20200715165709id_/https://brenda.ru/about | снимок веб-архива 2020-07-15, © 2018 на странице |
| hh_about_mastersky | human | full | 2021-01-25 | https://web.archive.org/web/20210125140653id_/https://www.mastersky.pro/about/ | снимок веб-архива 2021-01-25 |
| hh_about_vkusleba | human | full | 2021-12-18 | https://web.archive.org/web/20211218023818id_/https://bakeryvkushleba.ru/ | снимок веб-архива 2021-12-18 |
| hh_doc_amocrm | human | tech | 2020-12-09 | https://web.archive.org/web/20201209093109id_/https://www.amocrm.ru/developers/content/api/account | снимок веб-архива 2020-12-09, © 2009-2020 на странице |
| hh_doc_bitrix | human | tech | 2021-01-23 | https://web.archive.org/web/20210123145130id_/https://dev.1c-bitrix.ru/rest_help/ | снимок веб-архива 2021-01-23, © 2001-2021 на странице |
| hh_doc_ymaps | human | tech | 2020-12-22 | https://web.archive.org/web/20201222004809id_/https://yandex.ru/dev/maps/jsapi/doc/2.1/quick-start/index.html/ | снимок веб-архива 2020-12-22, © 2020 на странице |
| hh_land_argo | human | full | 2021-01-27 | https://web.archive.org/web/20210127090751id_/https://www.argoclass.ru/ | снимок веб-архива 2021-01-27, лендинг автошколы |
| hh_land_avtoorel | human | full | 2021-01-21 | https://web.archive.org/web/20210121230017id_/http://avtoshkolaorel.ru/ | снимок веб-архива 2021-01-21, лендинг автошколы |
| hh_land_beowulf | human | full | 2021-01-19 | https://web.archive.org/web/20210119180955id_/https://beowulf.school/ | снимок веб-архива 2021-01-19, лендинг школы английского (отзывы датированы 2017-2019) |
| hh_land_lavka | human | full | 2021-01-24 | https://web.archive.org/web/20210124162327id_/http://lavkapekarya.ru/ | снимок веб-архива 2021-01-24, лендинг сети булочных (в тексте новости от декабря 2020) |
| hh_letter_arenda | human | full | 2020-04-23 | https://vc.ru/legal/122465-shablon-pisma-ob-umenshenii-arendnoi-platy-v-svyazi-s-koronavirusom | datePublished 2020-04-23 на странице vc.ru |
| hh_letter_buslik | human | full | 2020-03-24 | https://probusiness.io/management/6906-gendirektor-buslik-napisal-partneram-pismo-o-fors-mazhore-posmotrite-vozmozhno-i-vam-pridetsya-eto-sdelat.html | datePublished 2020-03-24 в разметке страницы |
| hh_letter_tinkov | human | full | 2017-01-20 | https://vc.ru/flood/21435-tinkoff-nocoffee | datePublished 2017-01-20 на странице vc.ru |
| hh_news_chelkp | human | full | 2022-03-24 | https://www.chel.kp.ru/online/news/4678784/ | article:published_time 2022-03-24 в разметке страницы KP.RU Челябинск |
| hh_news_ngs | human | full | 2021-04-17 | https://ngs.ru/text/gorod/2021/04/17/69869948/ | datePublished 2021-04-17 в разметке страницы НГС (Новосибирск) |
| hh_news_perm_topol | human | full | 2019-12-05 | https://59.ru/text/gorod/2019/12/05/66385414/ | datePublished 2019-12-05 в разметке страницы 59.ru (Пермь) |

## Источники

| Файл | Метка | Профиль | Дата | Источник | Происхождение |
|------|-------|---------|------|----------|---------------|
| h_ainl_abstract_0 | human | science | до 2025 | https://huggingface.co/datasets/iis-research-team/AINL-Eval-2025 (dev_full.csv) | метка датасета `abstract`, аннотация из статьи |
| h_ainl_abstract_1 | human | science | до 2025 | то же | то же |
| h_cl_chto_takoe_ling | human | science | 2019 | https://cyberleninka.ru/article/n/chto-takoe-lingvistika | дата публикации на странице |
| h_cl_formal_ling | human | science | 2017 | https://cyberleninka.ru/article/n/russkiy-yazyk-i-formalnaya-lingvistika | то же |
| h_cl_ru_internet | human | science | 2013 | https://cyberleninka.ru/article/n/russkiy-yazyk-i-internet | то же |
| h_full_tinkoff_about | human | full | 2021-01-22 | https://web.archive.org/web/20210122203717id_/https://www.tinkoff.ru/about/ | снимок веб-архива |
| h_github_readme_ru | human | tech | 2019-09-01 | https://github.com/devopshq/ExampleProject/blob/master/README.md | последний коммит в README, есть «Введение» |
| h_gov_press | human | full | 2021-04-15 | http://government.ru/news/42000/ | дата в тексте, канцелярит |
| h_habr_interview | human | post | 2020-09-12 | https://habr.com/ru/post/490000/ | дата публикации на странице |
| h_habr_qsoa | human | tech | 2020-11-08 | https://habr.com/ru/post/525000/ | то же |
| h_habr_revit | human | tech | 2021-04-01 | https://habr.com/ru/post/550000/ | то же, пункты с жирным заголовком |
| h_habr_webrtc | human | tech | 2019-12-13 | https://habr.com/ru/post/480000/ | то же |
| h_legal_ivi_agreement | human | legal | 2018-01-26 | https://web.archive.org/web/20210211005936id_/https://www.ivi.ru/info/agreement | редакция в тексте, снимок 2021 |
| h_legal_yandex_tos | human | legal | 2020-12-31 | https://web.archive.org/web/20201231212051id_/https://yandex.ru/legal/rules/ | снимок веб-архива |
| h_lj_dublin | human | post | 2016-05-22 | https://travel-fanat.livejournal.com/131404.html | дата записи ЖЖ |
| h_lj_slovakia | human | post | 2016-05-08 | https://travel-fanat.livejournal.com/129440.html | то же |
| h_rt_press | human | full | 2021-11-09 | https://www.company.rt.ru/press/news_ir/news/d461086/ | пресс-релиз, дата в тексте |
| h_tg_tema_380 | human | post | 2018-02-15 | https://t.me/temalebedev/380 | дата сообщения |
| h_tg_tema_388 | human | post | 2018-02-16 | https://t.me/temalebedev/388 | то же |
| h_vc_news_x5 | human | full | 2021-01-22 | https://vc.ru/trade/199693-vladelec-pyaterochek-otchitalsya-o-roste-vyruchki-cifrovyh-servisov-pochti-v-pyat-raz-v-2020-godu-do-20-1-mlrd-rubley | дата публикации на странице |
| h_vc_smartofood | human | full | 2021-11-25 | https://vc.ru/food/324612-smartofud-ot-malenkoi-dostavki-do-it-startapa-kak-restoranu-konkurirovat-na-ravnyh-s-krupnym-brendom | то же |
| m_ainl_gemma_0 | machine | science | 2025 | https://huggingface.co/datasets/iis-research-team/AINL-Eval-2025 (dev_full.csv) | метка датасета: gemma-2-27b |
| m_ainl_gpt_0 | machine | science | 2025 | то же | gpt-4-turbo |
| m_ainl_gpt_1 | machine | science | 2025 | то же | gpt-4-turbo |
| m_ainl_llama_0 | machine | science | 2025 | то же | llama-3.3-70b |
| m_llmtrace_gemma_article | machine | post | 2025 | https://huggingface.co/datasets/iitolstykh/LLMTrace_detection (valid.jsonl, topic_id 6c3fbeeae71b593c3464002d5851aa26) | метка датасета: gemma-2-27b-it |
| m_llmtrace_gigachat_article | machine | tech | 2025 | то же, topic_id f2538507b5c235eb37017e4231cdf037 | gigachat |
| m_llmtrace_gigachatmax_news | machine | full | 2025 | то же, topic_id 38b316e73360ee073604f75e6c67e2cb | GigaChat-Max |
| m_llmtrace_gpt35_news | machine | full | 2025 | то же, topic_id 4628efb60bdc1511abf22ae8be8bbafc | gpt-3.5 |
| m_llmtrace_yagpt_article | machine | full | 2025 | то же, topic_id 717757ef60b4e7abde626042f399b5b8 | yagpt |
| m_vc_polar | machine | post | 2025-03-26 | https://vc.ru/offline/1886866-kak-ya-promenyal-ofis-na-polyarnuyu-stanciyu-zapiski-aitishnika-vo-ldah | автор признался в https://dtf.ru/chatgpt/3804931 (2025-06-02): текст написал Claude, правка лёгкая |
| m_wiki_prgen_examples | machine | full | 2025 | https://ru.wikipedia.org/wiki/Википедия:Признаки_сгенерированности_текста | шесть примеров со страницы, склеены в один файл |
