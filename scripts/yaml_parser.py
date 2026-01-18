#!/usr/bin/python3

import re
import os


# Регулярные выражения для проверки структуры файла
major_vers_pattern = r'^(\d+):$'  # Мажорная версия представлена числом (одна или более цифра), без отступа
task_pattern = r'^  - task: '  # Шаблон любой строки, начинающийся с `  - task: ...`, отступ 2 пробела
task_extended_pattern = r'^  - task: http(.+)$'  # Расширенный формат шаблона объявления задачи
arch_pattern = r'^    arch: (stm32|avr|at32)(, (stm32|avr|at32))*$'  # Шаблон, описывающий строку с архитектурой. Пример совпадения: `    arch: stm32, avr`.
task_type_pattern = r'^    (feature|bug|internal|info): \|$'  # Тип задачи - объявление многострочного описания, отступ 4 пробела
description_initial_pattern = r'^      \S(.*)'  # Первая строка многострочного описания, отступ ровно 6 пробелов с последующим непробельным символом
description_pattern = r'^      (.*)'  # Следующие строки описания (могут быть разделителем абзацев, т.е. 0 символов после отступа), отступ ровно 6 пробелов
separator_pattern = r'^$'  # Пустая строка - разделитель между словарями категорий `- task` и/или `- release/prerelease`

# В проекте ktr/modem есть релиз и предрелиз
# Шаблон любой строки, начинающийся с `  - release: ...` или `  - prerelease: ...`, отступ 2 пробела
release_pattern = r'^  - (release|prerelease): '
# # Расширенный формат шаблона объявления объявления релиза/предрелиза,
# после двоеточия пробел и число из одной и более цифры, отступ 2 пробела.
# Пример совпадения: `  - prerelease: 123`
release_extended_pattern = r'^  - (release|prerelease): (\d+)$'

# Шаблон поля дата `    date: dd.mm.yy`, отступ 4 пробела 
date_pattern = r'^    date: \d{2}\.\d{2}\.\d{2}$'  #
# Шаблон поля зависимостей `    dependencies: []` или `    dependencies:`, отступ 4 пробела
dependencies_pattern = r'^    dependencies:( \[\])*$'  #
# Шаблон поля base `    base: число` или `    base:`, отступ 4 пробела
# Минорная версия предрелиза, ставшая релизом
base_pattern = r'^    base: (\d+)*$'
# Шаблон поля protocol `    protocol: число`, отступ 4 пробела
protocol_pattern = r'^    protocol: (\d+)$'


# Обёртка над функцией вывода
def error(func):
    def wrapper(*args):
        # Префикс к каждому сообщению об ошибке
        new_args = [f"ERROR of file structure at {args[0]}:\n{args[1]}\nExpected: {arg}"
                    for arg in args[2:]]
        return func(*new_args)
    return wrapper


# Декоратор к функции print
@error
def error_print(*args):
    print(*args)


# Класс парсера ченжлога
class YamlParser:
    def __init__(self):
        self.line_number = 0  # Номер строки в читаемом файле
        self.reset_state()

    def reset_state(self):
        '''Сброс состояния флагов'''
        # Флаги для индикации состояния парсера
        self.state = {
            'major_ver': False,
            'task': False,
            'arch': False,
            'type': False,
            'description': False,
            'release': False,
            'date': False,
            'dependencies': False,
            'base': False,
            'protocol': False
        }

    # Парсинг прочитанной строки
    def parse_line(self, string):
        '''
        Парсит строку и обновляет состояние флагов.

        В зависимости от формата строки и состояния флагов, обновляет внутренние флаги и
        вызывает соответствующие методы для дальнейшего парсинга.
        Если это не номер мажорной версии, то либо это словарь категории описания задачи (- task), либо релиза (- release)

        Параметры:
        ----------
        string : str
            Строка, которую необходимо проверить на соответствие формату.
        '''
        if re.match(major_vers_pattern, string):
            self.state['major_ver'] = True
        elif not self.state['task'] and not self.state['release']:
            self.parse_initial(string)
        elif self.state['task']:
            self.parse_task(string)
        elif self.state['release']:
            self.parse_release(string)

    def parse_initial(self, string):
        '''
        Парсит начальную строку в объявлении словаря категории task или release и обновляет состояние.

        В зависимости от формата строки, устанавливает соответствующие флаги (`task` или `release`).
        Если строка не соответствует ни одному из ожидаемых форматов,
        вызывается метод `validate_initial` для проверки корректности строки.

        Параметры:
        ----------
        string : str
            Строка, которую необходимо проверить на соответствие формату.

        Исключения:
        -----------
        Вызывает метод `validate_initial`, если строка не соответствует формату задачи
        или релиза.
        '''
        if re.match(task_extended_pattern, string):
            self.state['task'] = True
        elif re.match(release_extended_pattern, string):
            self.state['release'] = True
        else:
            self.validate_initial(string)  # Если не найдено соответствий (task, release)

    # Выявление ошибки
    def validate_initial(self, string):
        '''
        Проверяет корректность начальной строки в объявлении словаря категории task или release
        Строка должна начинаться с двух пробелов и соответствует одному из следующих шаблонов:
        - `  - task: <link-to-task>`
        - `  - release: <minor-version-number>`

        Если строка не соответствует этим критериям, вызывается метод `raise_error`
        с соответствующим сообщением об ошибке.

        Параметры:
        ----------
        string : str
            Строка, которую необходимо проверить на соответствие формату.

        Исключения:
        -----------
        Вызывает метод `raise_error`, если строка не соответствует требованиям:
            - Неправильный отступ (не 2 пробела перед задачей или релизом).
            - Неверный формат задачи или релиза.
        '''
        if not re.match(r'^  \S', string):  # Неправильный отступ для категории
            self.raise_error(string, "2 spaces `  ` before {task,release}")
        if not re.match(task_pattern, string) and not re.match(release_pattern, string):
            self.raise_error(string, "`  - {task,release}:`")
        elif re.match(task_pattern, string):
            self.raise_error(string, "`  - task: <link-to-task>`")
        elif re.match(release_pattern, string):
            self.raise_error(string, "`  - release: <minor-version-number>`")

    # Чтение словаря категории task
    def parse_task(self, string):
        '''
        Парсит строку, представляющую задачу и обновляет состояние флагов.

        Проверяет отступы, архитектуру (arch), тип задачи и описание,
        В случае обнаружения ошибок вызывается метод `raise_error`.

        Параметры:
        ----------
        string : str
            Строка, которую необходимо проанализировать как задачу.

        Исключения:
        -----------
        Вызывает метод `raise_error`, если строка не соответствует требованиям:
            - Неправильный отступ (не 4 пробела).
            - Отсутствие или неверный формат архитектуры.
            - Отсутствие или неверный формат типа задачи.
            - Отсутствие или неверный формат описания.
        '''
        # Проверка на отступ (текущая строка является ключом в словаре и
        # не является описанием (значение поля feature/bug/internal/info)
        # или разделителем словарей - пустой строкой)
        if not re.match(r'^    \S', string) and \
            not self.state['type'] and \
                not re.match(separator_pattern, string):
            self.raise_error(string, "indent 4 spaces `    `")

        if re.match(arch_pattern, string):
            self.state['arch'] = True
            return
        elif not self.state['arch']:
            self.raise_error(string, "`    arch: {stm32,avr,at32}`")

        if self.state['arch']:
            if re.match(task_type_pattern, string):
                self.state['type'] = True
                return
            elif not self.state['type']:
                self.raise_error(string, "`    {feature,bug,internal}: |`")

            if self.state['type']:
                # Если прочитана пустая строка, то
                # словарь task закончился => сброс состояния
                if re.match(separator_pattern, string) and self.state['description']:
                    self.reset_state()
                    return

                if re.match(description_initial_pattern, string):
                    self.state['description'] = True
                    return
                elif self.state['description'] and re.match(description_pattern, string):
                    return
                else:
                    self.raise_error(string, "`      <description>`")

    def parse_release(self, string):
        '''
        Расширяет функциональность базового метода `parse_release`, добавляя
        дополнительные проверки для полей типа, протокола и описания.

        Параметры:
        ----------
        string : str
            Входная строка, представляющая строку информации о релизе, соответствующая определённому
            формату с отступами и обязательными/необязательными полями.

        Исключения:
        -----------
        Вызывает метод `raise_error`, если строка не соответствует требованиям:
            - Неправильный отступ (не 4 пробела).
            - Отсутствие даты или неверный формат даты.
            - Отсутствие зависимостей после указания даты.
            - Отсутствие протокола после указания зависимостей.
            - Неверный формат описания, если оно есть.
        '''
        if not re.match(r'^    \S', string) and \
            not self.state['type'] and \
                not re.match(separator_pattern, string):
            self.raise_error(string, "indent 4 spaces `    `")

        if re.match(date_pattern, string):
            self.state['date'] = True
            return
        elif not self.state['date']:
            self.raise_error(string, "`    date: <dd.mm.yy>`")

        if self.state['date']:
            if re.match(dependencies_pattern, string):
                self.state['dependencies'] = True
                return
            elif re.match(base_pattern, string):  # Необязательное поле base
                self.state['base'] = True
                return
            elif not self.state['dependencies']:
                self.raise_error(string, "`    dependencies:`")

            if self.state['dependencies']:
                if re.match(protocol_pattern, string):  # Обязательное поле protocol
                    self.state['protocol'] = True
                    return
                elif not self.state['protocol']:
                    self.raise_error(string, "`    protocol: <number-of-protocol>`")

                if self.state['protocol']:
                    # Если в словаре - release есть необязательное поле info с многострочным описанием
                    if re.match(task_type_pattern, string):
                        self.state['type'] = True
                        return
                    else:
                        if re.match(separator_pattern, string):
                            self.reset_release_state()

                    if self.state['type']:
                        if re.match(separator_pattern, string) and self.state['description']:
                            self.reset_release_state()
                            return

                        if re.match(description_initial_pattern, string):
                            self.state['description'] = True
                            return
                        elif self.state['description'] and re.match(description_pattern, string):
                            return
                        else:
                            self.raise_error(string, "`      <description>`")

    # Сброс состояния флагов
    def reset_release_state(self):
        for key in ['release', 'date', 'dependencies', 'base', 'protocol', 'description', 'type']:
            self.state[key] = False

    # Установить номер текущей строки
    def set_current_line_number(self, number: int):
        self.line_number = number

    # Вывести лог об ошибке с указанием номера строки
    def raise_error(self, line: str, message: str):
        error_print(os.readlink('/proc/self/fd/0') + f', line {self.line_number}', f"`{line}`", message)
        exit(1)


def parse_yaml():
    parser = ModemYamlParser()

    try:
        enumerator = 0
        while True:
            enumerator += 1
            # Считываение построчно из stdin (changelog.yaml)
            # ./yaml_parser.py < changelog.yaml
            line = input()
            parser.set_current_line_number(enumerator)
            parser.parse_line(line)
    except EOFError:
        print("Parsed successfully!")


if __name__ == "__main__":
    parse_yaml()
