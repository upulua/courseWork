import spacy
from pdfminer.layout import LTFigure, LTRect, LTCurve
from pdfminer.high_level import extract_pages
from pdfminer.high_level import extract_text
from pyate import combo_basic, basic, cvalues, weirdness
from pyate.term_extraction import TermExtraction
import pandas as pd
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from io import StringIO
import re
import copy
from os import listdir
from os.path import isfile, join


TermExtraction.set_language("ru", "ru_core_news_md")

path = '../ВКР ИГСУ/Баклавриат/ЗР/'


def get_all_files(path):
    files = [(path + f) for f in listdir(path) if isfile(join(path, f))]
    return files


def is_number(n):
    try:
        float(n)
    except ValueError:
        return False
    return True


def get_content(line, is_last_part_ended):
    word = str()
    is_this_part_ended = False
    is_new_word: bool = False
    is_only_digits = False
    # print(f'given line {line}\n')
    for item in line:

        if item.isdigit() and (word == "" or is_only_digits):
            word += item
            is_new_word = True
            is_only_digits = True
        if (item >= 'а' and item <= 'я') or (item >= 'А' and item <= 'Я') or item == ':' or item == '-' \
                or (item >= 'a' and item <= 'z') or (item >= 'A' and item <= 'Z') or item == '(' or item == ')':
            if is_new_word:
                word += ' '
                is_new_word = False
            word += item
            is_only_digits = False
        if item == ' ' and not word == "":
            is_new_word = True
        if item == '.' and not word == "" and not is_only_digits:
            is_this_part_ended = True
        elif is_only_digits and item == '.':
            word += item
    word = word.strip()
    if word.lower() == 'содержание':
        is_this_part_ended = True
    if is_number(word) and not is_last_part_ended:
        word = ""
        is_this_part_ended = True
    # print('"{}", {}'.format(word, is_this_part_ended))
    return word, is_this_part_ended


def get_array_content(path):
    is_last_part_ended = True
    table = []
    for page_layout in extract_pages(path):
        for element in page_layout:
            if not isinstance(element, LTFigure) and not isinstance(element, LTRect) and not isinstance(element, LTCurve):
                line = element.get_text()
                word, is_this_part_ended = get_content(
                    line, is_last_part_ended)
                if word.lower() == 'содержание':
                    table.clear()
                    is_last_part_ended = True
                if is_last_part_ended:
                    table.append(word)
                else:
                    table[-1] = table[-1] + ' ' + word
                is_last_part_ended = is_this_part_ended
                if table[-1].lower() == 'библиографический список':
                    # print('TABLE IS DONE\n')
                    for item in table:
                        item = item.strip()
                    return table


def get_pdf_list_strings(path):
    pages_text = []
    for page in extract_pages(path):
        page_text = ""
        for element in page:
            if not isinstance(element, LTFigure) and not isinstance(element, LTRect) and not isinstance(element, LTCurve):
                text = element.get_text()
                page_text += text
        pages_text.append(page_text)

    return pages_text


def get_content_boundaries(l):
    name_begin = ""
    name_end = ""
    id_begin = -1
    id_end = -1
    for id, content in enumerate(l):
        if id_begin == -1 and content[0] == '1':
            id_begin = id
        if id_end == -1 and content[0] == '2':
            id_end = id
    return id_begin, id_end


def del_numbers_from_content(l):
    new_l = []
    for item in l:
        id_del = 0
        is_char_seen = False
        for id, char in enumerate(item):
            if (char.isdigit() or char == '.') and not is_char_seen:
                id_del += 1
            elif (char >= 'а' and char <= 'я') or (char >= 'А' and char <= 'Я'):
                is_char_seen = True

        i = copy.deepcopy(item)
        i = i[id_del:].strip()
        new_l.append(i)

    for item in new_l:
        item.strip()
    return new_l


def del_headers(id_begin, id_end, l_headers, paragraph):
    new_par = ""
    #  what if there's only one header?
    if id_end - id_begin == 1:
        new_par = copy.deepcopy(
            paragraph[id_begin + len(l_headers[id_begin]):])
        return new_par
    for i in range(id_begin, id_end - 1):
        pos1 = paragraph.find(l_headers[i])
        pos2 = paragraph.find(l_headers[i + 1])
        if pos1 != -1 and pos2 != -1:
            text = copy.deepcopy(paragraph[pos1 + len(l_headers[i]): pos2])
            new_par += text
    return new_par


def find_definitions(paragraph):
    definitions = []
    pos_text = []
    patterns = ["NOUN – это NOUN", "NOUN – это VERB NOUN",
                "NOUN – это ADJ NOUN", "NOUN – это ADJ ADJ NOUN", "NOUN – это VERB ADJ NOUN",
                "NOUN VERB – это NOUN", "NOUN VERB – это VERB NOUN", "NOUN VERB – это ADJ NOUN",

                "PROPN – это NOUN", "PROPN – это VERB NOUN",
                "PROPN – это ADJ NOUN", "PROPN – это ADJ ADJ NOUN", "PROPN – это VERB ADJ NOUN",
                "PROPN VERB – это NOUN", "PROPN VERB – это VERB NOUN", "PROPN VERB – это ADJ NOUN"]

    for sent in paragraph.sents:
        s = ""
        for word in sent:
            if word.pos_ == 'SPACE':
                s += " "
            elif word.lemma_.lower() == 'это':
                if len(s):
                    if s[-1] != ' ':
                        s += ' '
                s += word.lemma_.lower()
            elif word.pos_ == 'PUNCT' and (word.lemma_ == '–' or word.lemma_ == '-'):
                if len(s):
                    if s[-1] != ' ':
                        s += ' '
                s += '–'
            else:
                if len(s):
                    if s[-1] != ' ':
                        s += ' ' + word.pos_
                    else:
                        s += word.pos_
                else:
                    s += word.pos_
        pos_text.append(s)

    sents = [sent for sent in paragraph.sents]
    for sent_idx, sent in enumerate(pos_text):
        for pattern in patterns:
            if len(re.findall(pattern, sent)):
                print(
                    f'I think this sentence is a definition!\n{sents[sent_idx]}\n')
                definitions.append(sents[sent_idx])
    return definitions


def main(path):
    text = extract_text(path)
    table_of_contents_with_numbers = get_array_content(path)
    table_of_contents_without_numbers = del_numbers_from_content(
        table_of_contents_with_numbers)

    id_begin, id_end = get_content_boundaries(
        table_of_contents_with_numbers)
    # data = get_pdf_list_strings(file)
    name_begin = table_of_contents_without_numbers[id_begin]
    name_end = table_of_contents_without_numbers[id_end]
    text_without_enter = re.sub('\n', '', text)
    begin = text_without_enter.find(name_begin)
    end = text_without_enter.find(name_end)
    theoretical_part = text_without_enter[begin:end]
    #  delete headers
    theoretical_part = del_headers(
        id_begin, id_end, table_of_contents_without_numbers, theoretical_part)
    nlp = spacy.load('ru_core_news_lg')
    t = nlp(theoretical_part)
    res = find_definitions(t)
    print(f'Work with {path} was successful\n')
    return res


error_files = ['ВКР ИГСУ/Баклавриат/ФГМУ/Кувшинчикова_ВКР.pdf',
               'ВКР ИГСУ/Баклавриат/ФГМУ/ВКР_ОЧИРОВА.pdf', 'ВКР ИГСУ/Баклавриат/ФГМУ/ВКР_Щевелева.pdf', 'ВКР ИГСУ/Баклавриат/ФГМУ/ВКР_Рудякова.pdf']
files = get_all_files(path)
all_files = 0
def_found = 0
for file in files:
    if file not in error_files:
        print(file)
        all_files += 1
        if main(file):
            def_found += 1

print(f'Files checked: {all_files}, where definitions were found: {def_found}')
# file = path + 'VKR_Shtepa.pdf'
# main(file)

# find_terms(b)

# print("basic")
# print(basic(theoretical_part).sort_values(ascending=False))
# print("\n")
# print("combo basic")
# print(combo_basic(theoretical_part).sort_values(ascending=False))
# print("\n")
# print("cvalues")
# print(cvalues(theoretical_part).sort_values(ascending=False))
# print("\n")
# print("weirdness")
# print(weirdness(theoretical_part).sort_values(ascending=False))

# from corus import load_wiki
# path = '/home/upulua/.local/lib/python3.8/site-packages/corus/data/ruwiki-latest-pages-articles.xml.bz2'

# records = load_wiki(path)

# # path_for_general_domain = '/home/upulua/.local/lib/python3.8/site-packages/pyate'

# f = open("/home/upulua/.local/lib/python3.8/site-packages/pyate/default_general_domain.ru", "w")
# i = 0
# f.write(",SECTION_TEXT\n")

# for record in records:
#     if i > 5000:
#         break
#     text = record.text
#     i = i + 1
#     s = '{0},"{{{1}}}"\n'
#     f.write(s.format(i, text))

# f.close()

# print(next(records))
# # print(list(records))
# path = "/home/upulua/.local/lib/python3.8/site-packages/pyate/default_general_domain.ru"
# path2 = "/home/upulua/.local/lib/python3.8/site-packages/pyate/default_general_domain_2.ru"
# with open(path, 'r') as r, open(path2, 'x') as o:
#     for line in r:
#         if line.strip():
#             o.write(line)
