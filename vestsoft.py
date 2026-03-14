#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vest Soft - Консольный менеджер Telegram аккаунтов
Управление только цифрами
Запуск: python vsoft.py
"""

import os
import sys
import json
import asyncio
import random
import string
import shutil
import time
from datetime import datetime
from pathlib import Path

# Импортируем Pyrogram
try:
    from pyrogram import Client
    from pyrogram.errors import (
        ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid,
        SessionPasswordNeeded, FloodWait, PeerIdInvalid,
        UsernameNotOccupied, UsernameInvalid, ChatAdminRequired,
        ChatWriteForbidden, UserAlreadyParticipant, MsgIdInvalid,
        MessageNotModified
    )
    from pyrogram.types import User, Dialog, Message
    from pyrogram.enums import ChatType
    from pyrogram import filters
    from pyrogram.raw import functions
    from pyrogram.raw.types import ReactionEmoji
except ImportError:
    print("[!] Pyrogram не установлен. Установите: pip install pyrogram")
    sys.exit(1)

# Константы
DATA_DIR = "data"
SESSIONS_DIR = "sessions"
TEMP_SESSIONS_DIR = "temp_sessions"
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
MAX_ACCOUNTS = 10
MAX_GROUPS_CHANNELS = 50
MAX_BOTS = 5
MAX_MAILING_CHATS = 20
MAX_MAILING_ACCOUNTS = 5
MAX_REACTION_CHATS = 10
REACTION_EMOJI = "❤️"

# Создаем необходимые папки
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_SESSIONS_DIR, exist_ok=True)

# Глобальные переменные для фоновых задач
reaction_tasks = {}  # {task_id: task}
reaction_active = {}  # {chat_id: {account_phone: bool}}
reaction_lock = asyncio.Lock()

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def clear_screen():
    """Очистка экрана"""
    os.system('clear' if os.name == 'posix' else 'cls')

def load_json(file_path, default=None):
    """Загрузка JSON из файла"""
    if default is None:
        default = {}
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[!] Ошибка загрузки {file_path}: {e}")
    return default

def save_json(file_path, data):
    """Сохранение JSON в файл"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[!] Ошибка сохранения {file_path}: {e}")
        return False

def generate_random_name(length=8, suffix="bot"):
    """Генерация случайного имени для бота"""
    letters = string.ascii_lowercase
    random_part = ''.join(random.choice(letters) for _ in range(length))
    return f"{random_part}{suffix}"

def get_next_session_name():
    """Получение следующего доступного имени сессии"""
    sessions = load_json(SESSIONS_FILE, [])
    used_numbers = []
    for acc in sessions:
        if acc.get("session_name", "").startswith("acc_"):
            try:
                num = int(acc["session_name"].replace("acc_", ""))
                used_numbers.append(num)
            except:
                pass
    
    for i in range(1, MAX_ACCOUNTS + 1):
        if i not in used_numbers:
            return f"acc_{i}"
    return None

def format_number(phone):
    """Форматирование номера телефона"""
    if phone and not phone.startswith('+'):
        return f"+{phone}"
    return phone

def get_current_time():
    """Получение текущего времени в формате строки"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def print_header(title):
    """Печать заголовка"""
    clear_screen()
    print("=" * 60)
    print(f"   {title}")
    print("=" * 60)

def print_success(text):
    """Печать успешного сообщения"""
    print(f"✅ {text}")

def print_error(text):
    """Печать сообщения об ошибке"""
    print(f"❌ {text}")

def print_info(text):
    """Печать информационного сообщения"""
    print(f"ℹ️ {text}")

def print_warning(text):
    """Печать предупреждения"""
    print(f"⚠️ {text}")

def get_number_input(prompt, min_val, max_val, default=None):
    """Получение числового ввода"""
    while True:
        try:
            if default:
                user_input = input(f"👉 {prompt} (по умолчанию {default}): ").strip()
                if user_input == "":
                    return default
            else:
                user_input = input(f"👉 {prompt}: ").strip()
            
            value = int(user_input)
            if min_val <= value <= max_val:
                return value
            else:
                print_error(f"Введите число от {min_val} до {max_val}")
        except ValueError:
            print_error("Введите число")
        except KeyboardInterrupt:
            print("\n")
            return None

def get_string_input(prompt, allow_empty=False):
    """Получение строкового ввода"""
    while True:
        try:
            value = input(f"👉 {prompt}: ").strip()
            if value or allow_empty:
                return value
            else:
                print_error("Введите значение")
        except KeyboardInterrupt:
            print("\n")
            return None

def wait_for_enter():
    """Ожидание нажатия Enter"""
    input("⏎ Нажмите Enter для продолжения...")

def cleanup_temp_sessions():
    """Очистка временных папок сессий"""
    try:
        shutil.rmtree(TEMP_SESSIONS_DIR)
        os.makedirs(TEMP_SESSIONS_DIR, exist_ok=True)
        time.sleep(0.5)  # Небольшая задержка после очистки
    except:
        pass

# ===================== КОНФИГУРАЦИЯ API =====================

def check_api_config():
    """Проверка наличия API конфигурации"""
    config = load_json(CONFIG_FILE)
    
    if not config.get("api_id") or not config.get("api_hash"):
        print_header("ПЕРВОНАЧАЛЬНАЯ НАСТРОЙКА")
        print("ℹ️ Для работы программы нужны API ID и API Hash")
        print("📝 Получить их можно на https://my.telegram.org/apps")
        print()
        
        while True:
            try:
                api_id = input("👉 Введите API ID: ").strip()
                if api_id.isdigit():
                    config["api_id"] = int(api_id)
                    break
                else:
                    print_error("API ID должен быть числом")
            except KeyboardInterrupt:
                print("\n")
                sys.exit(0)
        
        api_hash = input("👉 Введите API HASH: ").strip()
        config["api_hash"] = api_hash
        
        if save_json(CONFIG_FILE, config):
            print_success("Настройки сохранены!")
        else:
            print_error("Не удалось сохранить настройки")
            sys.exit(1)
        wait_for_enter()
    
    return config

# ===================== МЕНЕДЖЕР АККАУНТОВ =====================

async def add_account(api_id, api_hash):
    """Добавление нового аккаунта"""
    sessions = load_json(SESSIONS_FILE, [])
    
    if len(sessions) >= MAX_ACCOUNTS:
        print_error(f"Достигнут лимит аккаунтов ({MAX_ACCOUNTS})")
        wait_for_enter()
        return
    
    session_name = get_next_session_name()
    if not session_name:
        print_error("Не удалось создать имя сессии")
        wait_for_enter()
        return
    
    phone = get_string_input("Введите номер телефона (с '+')")
    if not phone:
        return
    phone = format_number(phone)
    
    session_path = os.path.join(SESSIONS_DIR, session_name)
    client = Client(session_path, api_id=api_id, api_hash=api_hash)
    
    try:
        await client.connect()
        
        print_info(f"Отправка кода на {phone}...")
        sent_code = await client.send_code(phone)
        print_success(f"Код отправлен")
        
        code = get_string_input("Введите код из Telegram")
        if not code:
            await client.disconnect()
            return
        
        try:
            await client.sign_in(phone, sent_code.phone_code_hash, code)
        except SessionPasswordNeeded:
            password = get_string_input("Введите пароль двухфакторной аутентификации")
            if not password:
                await client.disconnect()
                return
            await client.check_password(password)
        except PhoneCodeInvalid:
            print_error("Неверный код")
            await client.disconnect()
            wait_for_enter()
            return
        
        me = await client.get_me()
        
        account_data = {
            "phone": phone,
            "session_name": session_name,
            "user_id": me.id,
            "username": me.username or "",
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "premium": getattr(me, "is_premium", False)
        }
        
        sessions.append(account_data)
        save_json(SESSIONS_FILE, sessions)
        
        print_success(f"Аккаунт {me.first_name} успешно добавлен!")
        
    except FloodWait as e:
        print_error(f"Флуд-вейт: нужно подождать {e.value} секунд")
    except PhoneNumberInvalid:
        print_error("Неверный номер телефона")
    except ApiIdInvalid:
        print_error("Неверный API ID или HASH")
    except Exception as e:
        print_error(f"Ошибка: {e}")
    finally:
        await client.disconnect()
        wait_for_enter()

async def delete_account(account):
    """Удаление аккаунта"""
    print_warning(f"Вы уверены, что хотите удалить аккаунт {account['phone']}?")
    print("1. ✅ Да")
    print("2. ❌ Нет")
    
    choice = get_number_input("Выберите", 1, 2)
    if not choice:
        return
    
    if choice == 1:
        session_file = os.path.join(SESSIONS_DIR, f"{account['session_name']}.session")
        if os.path.exists(session_file):
            os.remove(session_file)
        
        sessions = load_json(SESSIONS_FILE, [])
        sessions = [acc for acc in sessions if acc["session_name"] != account["session_name"]]
        save_json(SESSIONS_FILE, sessions)
        
        print_success("Аккаунт удален")
    else:
        print_info("Отменено")
    
    wait_for_enter()

async def account_manager(api_id, api_hash):
    """Менеджер аккаунтов"""
    while True:
        sessions = load_json(SESSIONS_FILE, [])
        
        print_header(f"📱 МЕНЕДЖЕР АККАУНТОВ ({len(sessions)}/{MAX_ACCOUNTS})")
        
        if sessions:
            for idx, acc in enumerate(sessions):
                premium = "⭐" if acc.get("premium") else ""
                username = f"@{acc['username']}" if acc.get("username") else "нет юзернейма"
                print(f"{idx+1}. {acc['phone']} - {username} {premium}")
        else:
            print("📭 Нет добавленных аккаунтов")
        
        print("-" * 60)
        print("1. ➕ Добавить аккаунт")
        if sessions:
            print("2. ❌ Удалить аккаунт")
        print("3. 🔙 Назад в главное меню")
        print("-" * 60)
        
        choice = get_number_input("Выберите действие", 1, 3)
        if not choice:
            return
        
        if choice == 1:
            await add_account(api_id, api_hash)
        elif choice == 2 and sessions:
            acc_choice = get_number_input("Введите номер аккаунта для удаления", 1, len(sessions))
            if acc_choice:
                await delete_account(sessions[acc_choice-1])
        elif choice == 3:
            break

# ===================== ФУНКЦИИ: ГРУППЫ, КАНАЛЫ, БОТЫ =====================

async def select_account_for_function():
    """Выбор аккаунта для функции"""
    sessions = load_json(SESSIONS_FILE, [])
    
    if not sessions:
        print_error("Нет добавленных аккаунтов")
        wait_for_enter()
        return None
    
    print("👥 Выберите аккаунт:")
    for idx, acc in enumerate(sessions):
        premium = "⭐" if acc.get("premium") else ""
        username = f"@{acc['username']}" if acc.get("username") else "нет юзернейма"
        print(f"{idx+1}. {acc['phone']} - {username} {premium}")
    
    choice = get_number_input("Введите номер", 1, len(sessions))
    if choice:
        return sessions[choice-1]
    return None

async def select_multiple_accounts_for_function(max_accounts=MAX_MAILING_ACCOUNTS):
    """Выбор нескольких аккаунтов для функции"""
    sessions = load_json(SESSIONS_FILE, [])
    
    if not sessions:
        print_error("Нет добавленных аккаунтов")
        wait_for_enter()
        return None
    
    selected = []
    page = 0
    per_page = 10
    
    while True:
        print_header(f"👥 ВЫБОР АККАУНТОВ (выбрано: {len(selected)}/{max_accounts})")
        
        start = page * per_page
        end = min(start + per_page, len(sessions))
        
        print(f"📋 Аккаунты {start+1}-{end} из {len(sessions)}:")
        for i in range(start, end):
            acc = sessions[i]
            premium = "⭐" if acc.get("premium") else ""
            username = f"@{acc['username']}" if acc.get("username") else "нет юзернейма"
            mark = "✅ " if i in selected else ""
            print(f"{mark}{i+1}. {acc['phone']} - {username} {premium}")
        
        print("-" * 60)
        print("📝 Введите номер аккаунта для выбора/отмены выбора")
        print("0. ✅ Завершить выбор")
        print("N. ⏩ Следующая страница")
        print("P. ⏪ Предыдущая страница")
        print("C. ❌ Отмена")
        print("-" * 60)
        
        cmd = input("👉 Введите команду: ").strip().upper()
        
        if cmd == 'C':
            return None
        elif cmd == '0':
            if len(selected) == 0:
                print_error("Выберите хотя бы один аккаунт")
                continue
            break
        elif cmd == 'N':
            if end < len(sessions):
                page += 1
        elif cmd == 'P':
            if page > 0:
                page -= 1
        else:
            try:
                idx = int(cmd) - 1
                if 0 <= idx < len(sessions):
                    if idx in selected:
                        selected.remove(idx)
                        print_info(f"Аккаунт {sessions[idx]['phone']} удален из выбранных")
                    else:
                        if len(selected) < max_accounts:
                            selected.append(idx)
                            print_success(f"Аккаунт {sessions[idx]['phone']} добавлен")
                        else:
                            print_error(f"Максимум {max_accounts} аккаунтов")
                else:
                    print_error("Неверный номер")
            except ValueError:
                print_error("Неверная команда")
    
    return [sessions[i] for i in selected]

async def load_chats(client, account_phone, max_chats=100):
    """Загрузка чатов без перегрузки API"""
    chats = []
    try:
        async for dialog in client.get_dialogs():
            chat = dialog.chat
            chat_type = "👤" if chat.type == ChatType.PRIVATE else "👥" if chat.type == ChatType.GROUP else "📢"
            chat_name = chat.title if hasattr(chat, 'title') and chat.title else (chat.first_name or "Unknown")
            chats.append({
                "id": chat.id,
                "name": chat_name,
                "type": chat_type,
                "type_name": str(chat.type).split('.')[-1]
            })
            if len(chats) >= max_chats:
                break
            await asyncio.sleep(0.1)
    except Exception as e:
        print_error(f"Ошибка загрузки чатов: {e}")
    return chats

def format_chat_list(chats, page=0, per_page=10):
    """Форматирование списка чатов для отображения"""
    start = page * per_page
    end = min(start + per_page, len(chats))
    result = []
    for i in range(start, end):
        chat = chats[i]
        result.append(f"{i+1}. {chat['type']} {chat['name']} ({chat['type_name']})")
    return result, start, end

async def select_chat_for_function(client, account_phone):
    """Выбор одного чата для функции"""
    print_info("Загрузка чатов (это может занять некоторое время)...")
    chats = await load_chats(client, account_phone, max_chats=200)
    
    if not chats:
        print_error("Не удалось загрузить чаты")
        return None
    
    page = 0
    per_page = 10
    
    while True:
        print_header("📋 ВЫБОР ЧАТА")
        
        chat_list, start, end = format_chat_list(chats, page, per_page)
        print(f"📋 Чаты {start+1}-{end} из {len(chats)}:")
        for line in chat_list:
            print(line)
        
        print("-" * 60)
        print("📝 Введите номер чата для выбора")
        print("N. ⏩ Следующая страница")
        print("P. ⏪ Предыдущая страница")
        print("C. ❌ Отмена")
        print("-" * 60)
        
        cmd = input("👉 Введите команду: ").strip().upper()
        
        if cmd == 'C':
            return None
        elif cmd == 'N':
            if end < len(chats):
                page += 1
        elif cmd == 'P':
            if page > 0:
                page -= 1
        else:
            try:
                idx = int(cmd) - 1
                if 0 <= idx < len(chats):
                    return chats[idx]
                else:
                    print_error("Неверный номер")
            except ValueError:
                print_error("Неверная команда")

async def select_chats_for_mailing(client, account_phone):
    """Выбор нескольких чатов для рассылки"""
    print_info("Загрузка чатов (это может занять некоторое время)...")
    chats = await load_chats(client, account_phone, max_chats=200)
    
    if not chats:
        print_error("Не удалось загрузить чаты")
        return None
    
    selected = []
    page = 0
    per_page = 10
    
    while True:
        print_header(f"📬 ВЫБОР ЧАТОВ ДЛЯ РАССЫЛКИ (выбрано: {len(selected)}/{MAX_MAILING_CHATS})")
        
        chat_list, start, end = format_chat_list(chats, page, per_page)
        print(f"📋 Чаты {start+1}-{end} из {len(chats)}:")
        for line in chat_list:
            print(line)
        
        print("-" * 60)
        print("📝 Введите номер чата для выбора/отмены выбора")
        print("0. ✅ Завершить выбор")
        print("N. ⏩ Следующая страница")
        print("P. ⏪ Предыдущая страница")
        print("C. ❌ Отмена")
        print("-" * 60)
        
        cmd = input("👉 Введите команду: ").strip().upper()
        
        if cmd == 'C':
            return None
        elif cmd == '0':
            if len(selected) == 0:
                print_error("Выберите хотя бы один чат")
                continue
            break
        elif cmd == 'N':
            if end < len(chats):
                page += 1
        elif cmd == 'P':
            if page > 0:
                page -= 1
        else:
            try:
                idx = int(cmd) - 1
                if 0 <= idx < len(chats):
                    chat = chats[idx]
                    existing = next((item for item in selected if item['index'] == idx), None)
                    if existing:
                        selected = [item for item in selected if item['index'] != idx]
                        print_info(f"Чат {chat['name']} удален из выбранных")
                    else:
                        if len(selected) < MAX_MAILING_CHATS:
                            selected.append({
                                'index': idx,
                                'id': chat['id'],
                                'name': chat['name'],
                                'type': chat['type']
                            })
                            print_success(f"Чат {chat['name']} добавлен")
                        else:
                            print_error(f"Максимум {MAX_MAILING_CHATS} чатов")
                else:
                    print_error("Неверный номер")
            except ValueError:
                print_error("Неверная команда")
    
    return selected

async def select_chats_for_reactions(client, account_phone):
    """Выбор нескольких чатов для масс-реакций"""
    print_info("Загрузка чатов (это может занять некоторое время)...")
    chats = await load_chats(client, account_phone, max_chats=200)
    
    if not chats:
        print_error("Не удалось загрузить чаты")
        return None
    
    selected = []
    page = 0
    per_page = 10
    
    while True:
        print_header(f"❤️ ВЫБОР ЧАТОВ ДЛЯ РЕАКЦИЙ (выбрано: {len(selected)}/{MAX_REACTION_CHATS})")
        
        chat_list, start, end = format_chat_list(chats, page, per_page)
        print(f"📋 Чаты {start+1}-{end} из {len(chats)}:")
        for line in chat_list:
            print(line)
        
        print("-" * 60)
        print("📝 Введите номер чата для выбора/отмены выбора")
        print("0. ✅ Завершить выбор")
        print("N. ⏩ Следующая страница")
        print("P. ⏪ Предыдущая страница")
        print("C. ❌ Отмена")
        print("-" * 60)
        
        cmd = input("👉 Введите команду: ").strip().upper()
        
        if cmd == 'C':
            return None
        elif cmd == '0':
            if len(selected) == 0:
                print_error("Выберите хотя бы один чат")
                continue
            break
        elif cmd == 'N':
            if end < len(chats):
                page += 1
        elif cmd == 'P':
            if page > 0:
                page -= 1
        else:
            try:
                idx = int(cmd) - 1
                if 0 <= idx < len(chats):
                    chat = chats[idx]
                    existing = next((item for item in selected if item['index'] == idx), None)
                    if existing:
                        selected = [item for item in selected if item['index'] != idx]
                        print_info(f"Чат {chat['name']} удален из выбранных")
                    else:
                        if len(selected) < MAX_REACTION_CHATS:
                            selected.append({
                                'index': idx,
                                'id': chat['id'],
                                'name': chat['name'],
                                'type': chat['type']
                            })
                            print_success(f"Чат {chat['name']} добавлен")
                        else:
                            print_error(f"Максимум {MAX_REACTION_CHATS} чатов")
                else:
                    print_error("Неверный номер")
            except ValueError:
                print_error("Неверная команда")
    
    return selected

async def create_groups(api_id, api_hash):
    """Создание групп"""
    account = await select_account_for_function()
    if not account:
        return
    
    session_path = os.path.join(SESSIONS_DIR, account["session_name"])
    client = Client(session_path, api_id=api_id, api_hash=api_hash)
    
    try:
        await client.start()
        
        print_header("👥 СОЗДАНИЕ ГРУПП")
        
        title_template = get_string_input("Шаблон названия (можно использовать {num})")
        if not title_template:
            return
        
        count = get_number_input("Количество групп", 1, MAX_GROUPS_CHANNELS, 1)
        if not count:
            return
        
        delay = 10
        
        print("📦 Архивировать после создания?")
        print("1. ✅ Да")
        print("2. ❌ Нет")
        archive_choice = get_number_input("Выберите", 1, 2, 2)
        archive = (archive_choice == 1)
        
        print("👋 Отправлять приветствие?")
        print("1. ✅ Да")
        print("2. ❌ Нет")
        greeting_choice = get_number_input("Выберите", 1, 2, 2)
        send_greeting = (greeting_choice == 1)
        
        greeting_text = ""
        if send_greeting:
            greeting_text = get_string_input("Текст приветствия")
            if not greeting_text:
                return
        
        print_info(f"Начинаю создание {count} групп...")
        
        for i in range(1, count + 1):
            try:
                title = title_template.replace("{num}", str(i))
                print(f"🔄 Создание {i}/{count}: {title}")
                
                try:
                    group = await client.create_supergroup(title, "Создано через Vest Soft")
                    chat_id = group.id
                except AttributeError:
                    me = await client.get_me()
                    group = await client.create_group(title, me.id)
                    chat_id = group.id
                
                print_success(f"Группа создана: {title}")
                
                if archive:
                    try:
                        await client.archive_chats(chat_id)
                        print_info("📦 Группа архивирована")
                    except:
                        pass
                
                if send_greeting and greeting_text:
                    try:
                        await client.send_message(chat_id, greeting_text)
                        print_info("👋 Приветствие отправлено")
                    except:
                        pass
                
                if i < count:
                    print_info(f"⏳ Ожидание {delay} секунд...")
                    await asyncio.sleep(delay)
                    
            except FloodWait as e:
                print_warning(f"⚠️ Флуд-вейт: {e.value} секунд")
                await asyncio.sleep(e.value)
            except Exception as e:
                print_error(f"Ошибка: {e}")
        
        print_success("Создание групп завершено!")
        
    except Exception as e:
        print_error(f"Ошибка: {e}")
    finally:
        await client.stop()
        wait_for_enter()

async def create_channels(api_id, api_hash):
    """Создание каналов"""
    account = await select_account_for_function()
    if not account:
        return
    
    session_path = os.path.join(SESSIONS_DIR, account["session_name"])
    client = Client(session_path, api_id=api_id, api_hash=api_hash)
    
    try:
        await client.start()
        
        print_header("📢 СОЗДАНИЕ КАНАЛОВ")
        
        title_template = get_string_input("Шаблон названия (можно использовать {num})")
        if not title_template:
            return
        
        description = get_string_input("Описание (можно оставить пустым)", allow_empty=True)
        
        count = get_number_input("Количество каналов", 1, MAX_GROUPS_CHANNELS, 1)
        if not count:
            return
        
        delay = 10
        
        print("📦 Архивировать после создания?")
        print("1. ✅ Да")
        print("2. ❌ Нет")
        archive_choice = get_number_input("Выберите", 1, 2, 2)
        archive = (archive_choice == 1)
        
        print("👋 Отправлять приветствие?")
        print("1. ✅ Да")
        print("2. ❌ Нет")
        greeting_choice = get_number_input("Выберите", 1, 2, 2)
        send_greeting = (greeting_choice == 1)
        
        greeting_text = ""
        if send_greeting:
            greeting_text = get_string_input("Текст приветствия")
            if not greeting_text:
                return
        
        print_info(f"Начинаю создание {count} каналов...")
        
        for i in range(1, count + 1):
            try:
                title = title_template.replace("{num}", str(i))
                print(f"🔄 Создание {i}/{count}: {title}")
                
                channel = await client.create_channel(title, description)
                chat_id = channel.id
                
                print_success(f"Канал создан: {title}")
                
                if archive:
                    try:
                        await client.archive_chats(chat_id)
                        print_info("📦 Канал архивирован")
                    except:
                        pass
                
                if send_greeting and greeting_text:
                    try:
                        await client.send_message(chat_id, greeting_text)
                        print_info("👋 Приветствие отправлено")
                    except:
                        pass
                
                if i < count:
                    print_info(f"⏳ Ожидание {delay} секунд...")
                    await asyncio.sleep(delay)
                    
            except FloodWait as e:
                print_warning(f"⚠️ Флуд-вейт: {e.value} секунд")
                await asyncio.sleep(e.value)
            except Exception as e:
                print_error(f"Ошибка: {e}")
        
        print_success("Создание каналов завершено!")
        
    except Exception as e:
        print_error(f"Ошибка: {e}")
    finally:
        await client.stop()
        wait_for_enter()

async def create_bots(api_id, api_hash):
    """Создание ботов"""
    account = await select_account_for_function()
    if not account:
        return
    
    session_path = os.path.join(SESSIONS_DIR, account["session_name"])
    client = Client(session_path, api_id=api_id, api_hash=api_hash)
    
    try:
        await client.start()
        
        print_header("🤖 СОЗДАНИЕ БОТОВ")
        
        bot_count = get_number_input("Сколько ботов создать", 1, MAX_BOTS, 1)
        if not bot_count:
            return
        
        botfather = "BotFather"
        
        for bot_num in range(1, bot_count + 1):
            try:
                print(f"\n🤖 Создание бота #{bot_num}")
                
                print("📤 Отправка /start...")
                await client.send_message(botfather, "/start")
                await asyncio.sleep(2)
                
                print("📤 Отправка /newbot...")
                await client.send_message(botfather, "/newbot")
                await asyncio.sleep(3)
                
                print("Хотите указать название вручную?")
                print("1. ✅ Да")
                print("2. 🔄 Сгенерировать")
                name_choice = get_number_input("Выберите", 1, 2, 2)
                
                if name_choice == 1:
                    bot_name = get_string_input("Введите название бота")
                    if not bot_name:
                        continue
                else:
                    bot_name = f"Bot_{generate_random_name(6, '')}"
                    print_info(f"Сгенерировано название: {bot_name}")
                
                print(f"📤 Отправка названия: {bot_name}")
                await client.send_message(botfather, bot_name)
                await asyncio.sleep(2)
                
                print("Хотите указать юзернейм вручную?")
                print("1. ✅ Да")
                print("2. 🔄 Сгенерировать")
                username_choice = get_number_input("Выберите", 1, 2, 2)
                
                if username_choice == 1:
                    bot_username = get_string_input("Введите юзернейм (должен оканчиваться на 'bot')")
                    if not bot_username:
                        continue
                    if not bot_username.endswith('bot'):
                        bot_username += 'bot'
                        print_info(f"Добавлено 'bot' в конец: {bot_username}")
                else:
                    bot_username = generate_random_name(8, "bot")
                    print_info(f"Сгенерирован юзернейм: {bot_username}")
                
                print(f"📤 Отправка юзернейма: @{bot_username}")
                await client.send_message(botfather, bot_username)
                
                print_success(f"Запрос на создание бота #{bot_num} отправлен!")
                print(f"📝 Название: {bot_name}")
                print(f"🔗 Юзернейм: @{bot_username}")
                
                if bot_num < bot_count:
                    print_warning("⏳ Задержка 200 секунд перед следующим ботом...")
                    for remaining in range(200, 0, -10):
                        print(f"⏳ Осталось: {remaining} секунд")
                        await asyncio.sleep(10)
                
            except FloodWait as e:
                print_warning(f"⚠️ Флуд-вейт: {e.value} секунд")
                await asyncio.sleep(e.value)
            except Exception as e:
                print_error(f"Ошибка: {e}")
        
        print_success(f"Создание {bot_count} ботов завершено!")
        
    except Exception as e:
        print_error(f"Ошибка: {e}")
    finally:
        await client.stop()
        wait_for_enter()

# ===================== ФУНКЦИЯ РАССЫЛКИ =====================

def create_temp_session_copy(original_session_name):
    """Создание временной копии сессии"""
    original_path = os.path.join(SESSIONS_DIR, f"{original_session_name}.session")
    
    if not os.path.exists(original_path):
        print_error(f"Файл сессии {original_session_name} не найден")
        return None
    
    timestamp = int(time.time())
    random_num = random.randint(1000, 9999)
    temp_name = f"temp_{original_session_name}_{timestamp}_{random_num}"
    temp_path = os.path.join(TEMP_SESSIONS_DIR, temp_name)
    
    try:
        shutil.copy2(original_path, f"{temp_path}.session")
        
        journal_file = f"{temp_path}.session-journal"
        with open(journal_file, 'w') as f:
            f.write('')
        
        return temp_name
    except Exception as e:
        print_error(f"Ошибка при создании копии сессии: {e}")
        return None

async def send_mailing_from_account(account, chat_ids, message, count, delay, mode, api_id, api_hash):
    """Отправка рассылки с одного аккаунта"""
    temp_session_name = create_temp_session_copy(account["session_name"])
    if not temp_session_name:
        print_error(f"❌ [{account['phone']}] Не удалось создать копию сессии")
        return 0, count * len(chat_ids)
    
    temp_session_path = os.path.join(TEMP_SESSIONS_DIR, temp_session_name)
    
    client = Client(
        temp_session_name,
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
        workdir=TEMP_SESSIONS_DIR
    )
    
    try:
        await client.connect()
        await client.get_me()
        
        print_info(f"\n📱 Аккаунт: {account['phone']}")
        
        total_sent = 0
        total_failed = 0
        
        if mode == 1:
            for chat in chat_ids:
                chat_name = chat['name']
                chat_id_val = chat['id']
                
                for msg_num in range(1, count + 1):
                    try:
                        await client.send_message(chat_id_val, message)
                        total_sent += 1
                        print(f"   ✅ [{account['phone']}] Отправлено {msg_num}/{count} в {chat_name}")
                        
                        if msg_num < count or chat != chat_ids[-1]:
                            await asyncio.sleep(delay)
                            
                    except FloodWait as e:
                        total_failed += 1
                        print_warning(f"   ⚠️ [{account['phone']}] Флуд-вейт {e.value}с в {chat_name}")
                        await asyncio.sleep(e.value)
                        
                    except Exception as e:
                        total_failed += 1
                        print_error(f"   ❌ [{account['phone']}] Ошибка в {chat_name}: {e}")
        
        else:
            all_messages = []
            for chat in chat_ids:
                for _ in range(count):
                    all_messages.append(chat)
            
            random.shuffle(all_messages)
            
            sent_count = 0
            total_messages = len(all_messages)
            
            for chat in all_messages:
                try:
                    chat_name = chat['name']
                    chat_id_val = chat['id']
                    
                    await client.send_message(chat_id_val, message)
                    total_sent += 1
                    sent_count += 1
                    print(f"   ✅ [{account['phone']}] Отправлено {sent_count}/{total_messages} (чат: {chat_name})")
                    
                    if sent_count < total_messages:
                        await asyncio.sleep(delay)
                        
                except FloodWait as e:
                    total_failed += 1
                    print_warning(f"   ⚠️ [{account['phone']}] Флуд-вейт {e.value}с")
                    await asyncio.sleep(e.value)
                    
                except Exception as e:
                    total_failed += 1
                    print_error(f"   ❌ [{account['phone']}] Ошибка: {e}")
        
        return total_sent, total_failed
        
    except Exception as e:
        print_error(f"❌ [{account['phone']}] Ошибка подключения: {e}")
        return 0, count * len(chat_ids)
    finally:
        try:
            await client.disconnect()
        except:
            pass
        
        try:
            session_file = f"{temp_session_path}.session"
            journal_file = f"{temp_session_path}.session-journal"
            
            if os.path.exists(session_file):
                os.remove(session_file)
            if os.path.exists(journal_file):
                os.remove(journal_file)
        except:
            pass

async def start_mailing(api_id, api_hash):
    """Запуск рассылки"""
    
    cleanup_temp_sessions()
    
    selected_accounts = await select_multiple_accounts_for_function(MAX_MAILING_ACCOUNTS)
    if not selected_accounts:
        return
    
    first_account = selected_accounts[0]
    session_path = os.path.join(SESSIONS_DIR, first_account["session_name"])
    
    if not os.path.exists(f"{session_path}.session"):
        print_error(f"Файл сессии для аккаунта {first_account['phone']} не найден")
        wait_for_enter()
        return
    
    client = Client(session_path, api_id=api_id, api_hash=api_hash)
    
    try:
        await client.start()
        
        selected_chats = await select_chats_for_mailing(client, first_account["phone"])
        if not selected_chats:
            return
        
        print_header("🔄 РЕЖИМ ОТПРАВКИ")
        print("1. 📋 Последовательно по чатам")
        print("   (сначала все сообщения в 1 чат, потом во 2 и т.д.)")
        print("2. 🎲 Рандомно по чатам")
        print("   (сообщения перемешиваются и отправляются в случайном порядке)")
        print("-" * 60)
        
        mode = get_number_input("Выберите режим", 1, 2, 1)
        if not mode:
            return
        
        print_header("📝 ТЕКСТ СООБЩЕНИЯ")
        message = get_string_input("Введите текст сообщения")
        if not message:
            return
        
        count = get_number_input("Сколько сообщений отправить в каждый чат", 1, 100, 1)
        if not count:
            return
        
        delay = get_number_input("Задержка между сообщениями (секунд)", 1, 3600, 5)
        if not delay:
            return
        
        print_header("✅ ПОДТВЕРЖДЕНИЕ РАССЫЛКИ")
        print(f"👥 Аккаунтов: {len(selected_accounts)}")
        for acc in selected_accounts:
            print(f"   📱 {acc['phone']}")
        print(f"💬 Чатов: {len(selected_chats)}")
        print(f"📝 Сообщений в чат: {count}")
        print(f"⏱ Задержка: {delay} сек")
        print(f"🔄 Режим: {'Последовательно' if mode == 1 else 'Рандомно'}")
        print(f"📊 Всего сообщений: {len(selected_accounts) * len(selected_chats) * count}")
        print()
        print("1. 🚀 Запустить рассылку")
        print("2. ❌ Отмена")
        
        choice = get_number_input("Выберите", 1, 2, 2)
        if choice != 1:
            return
        
        print_header("🚀 ЗАПУСК РАССЫЛКИ")
        
        chat_ids = [{'id': c['id'], 'name': c['name']} for c in selected_chats]
        grand_total_sent = 0
        grand_total_failed = 0
        
        for idx, account in enumerate(selected_accounts):
            print_info(f"\n📱 [{idx+1}/{len(selected_accounts)}] Начинаю рассылку с аккаунта {account['phone']}...")
            
            sent, failed = await send_mailing_from_account(
                account, chat_ids, message, count, delay, mode, api_id, api_hash
            )
            
            grand_total_sent += sent
            grand_total_failed += failed
            
            if account != selected_accounts[-1]:
                print_info("⏳ Переход к следующему аккаунту...")
                await asyncio.sleep(3)
        
        print_header("📊 ИТОГИ РАССЫЛКИ")
        print(f"✅ Успешно отправлено: {grand_total_sent}")
        print(f"❌ Ошибок: {grand_total_failed}")
        print(f"📱 Аккаунтов: {len(selected_accounts)}")
        print(f"💬 Чатов: {len(selected_chats)}")
        
    except Exception as e:
        print_error(f"Ошибка: {e}")
    finally:
        await client.stop()
        cleanup_temp_sessions()
        wait_for_enter()

# ===================== ФУНКЦИЯ МАСС-РЕАКЦИЙ =====================

async def set_reaction(client, chat_id, message_id):
    """Установка реакции на сообщение"""
    try:
        await client.send_reaction(chat_id, message_id, REACTION_EMOJI)
        return True
    except Exception as e1:
        try:
            await client.send_reaction(chat_id, message_id, [REACTION_EMOJI])
            return True
        except Exception as e2:
            try:
                peer = await client.resolve_peer(chat_id)
                await client.invoke(
                    functions.messages.SendReaction(
                        peer=peer,
                        msg_id=message_id,
                        reaction=[ReactionEmoji(emoticon=REACTION_EMOJI)]
                    )
                )
                return True
            except Exception as e3:
                return False

async def reaction_worker(account, chat_id, chat_name, api_id, api_hash, worker_id):
    """Фоновая задача для проставления реакций в одном чате"""
    global reaction_active
    
    temp_session_name = create_temp_session_copy(account["session_name"])
    if not temp_session_name:
        print_error(f"❌ [{account['phone']}] Не удалось создать копию сессии")
        return
    
    temp_session_path = os.path.join(TEMP_SESSIONS_DIR, temp_session_name)
    
    client = Client(
        temp_session_name,
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
        workdir=TEMP_SESSIONS_DIR
    )
    
    task_key = f"{account['phone']}_{chat_id}"
    
    try:
        await client.connect()
        me = await client.get_me()
        my_id = me.id
        
        async with reaction_lock:
            if chat_id not in reaction_active:
                reaction_active[chat_id] = {}
            reaction_active[chat_id][account['phone']] = True
        
        print_success(f"✅ [{account['phone']}] Запущен в чате {chat_name}")
        
        last_message_id = 0
        try:
            async for message in client.get_chat_history(chat_id, limit=1):
                last_message_id = message.id
        except:
            pass
        
        processed_ids = set()
        total_reactions = 0
        
        while True:
            async with reaction_lock:
                if not reaction_active.get(chat_id, {}).get(account['phone'], False):
                    break
            
            try:
                messages = []
                async for message in client.get_chat_history(chat_id, limit=20):
                    messages.append(message)
                
                for message in messages:
                    if message.id > last_message_id and message.id not in processed_ids:
                        if message.from_user and message.from_user.id != my_id:
                            has_reaction = False
                            if message.reactions:
                                for reaction in message.reactions.reactions:
                                    if reaction.emoji == REACTION_EMOJI:
                                        has_reaction = True
                                        break
                            
                            if not has_reaction:
                                success = await set_reaction(client, chat_id, message.id)
                                if success:
                                    total_reactions += 1
                                    user_name = message.from_user.first_name if message.from_user else "Unknown"
                                    print(f"❤️ [{account['phone']}] [{chat_name}] Реакция #{total_reactions} на сообщение от {user_name}")
                                await asyncio.sleep(0.5)
                        
                        processed_ids.add(message.id)
                        if message.id > last_message_id:
                            last_message_id = message.id
                
                if len(processed_ids) > 100:
                    processed_ids = set(list(processed_ids)[-100:])
                
                await asyncio.sleep(2)
                
            except FloodWait as e:
                print_warning(f"⚠️ [{account['phone']}] Флуд-вейт {e.value}с")
                await asyncio.sleep(e.value)
            except Exception as e:
                print_error(f"❌ [{account['phone']}] Ошибка: {e}")
                await asyncio.sleep(5)
        
        print_info(f"⏹ [{account['phone']}] Остановлен в чате {chat_name}. Всего реакций: {total_reactions}")
        
    except Exception as e:
        print_error(f"❌ [{account['phone']}] Ошибка в работе: {e}")
    finally:
        async with reaction_lock:
            if chat_id in reaction_active and account['phone'] in reaction_active[chat_id]:
                del reaction_active[chat_id][account['phone']]
                if not reaction_active[chat_id]:
                    del reaction_active[chat_id]
        
        try:
            await client.disconnect()
        except:
            pass
        
        try:
            session_file = f"{temp_session_path}.session"
            journal_file = f"{temp_session_path}.session-journal"
            
            if os.path.exists(session_file):
                os.remove(session_file)
            if os.path.exists(journal_file):
                os.remove(journal_file)
        except:
            pass

async def start_reactions(api_id, api_hash):
    """Запуск масс-реакций в нескольких чатах"""
    global reaction_tasks
    
    cleanup_temp_sessions()
    
    selected_accounts = await select_multiple_accounts_for_function(MAX_MAILING_ACCOUNTS)
    if not selected_accounts:
        return
    
    first_account = selected_accounts[0]
    session_path = os.path.join(SESSIONS_DIR, first_account["session_name"])
    
    if not os.path.exists(f"{session_path}.session"):
        print_error(f"Файл сессии для аккаунта {first_account['phone']} не найден")
        wait_for_enter()
        return
    
    client = Client(session_path, api_id=api_id, api_hash=api_hash)
    
    try:
        await client.start()
        
        selected_chats = await select_chats_for_reactions(client, first_account["phone"])
        if not selected_chats:
            return
        
        print_header("❤️ ЗАПУСК МАСС-РЕАКЦИЙ")
        print(f"👥 Аккаунтов: {len(selected_accounts)}")
        for acc in selected_accounts:
            print(f"   📱 {acc['phone']}")
        print(f"💬 Чатов: {len(selected_chats)}")
        for chat in selected_chats:
            print(f"   📋 {chat['name']}")
        print(f"❤️ Реакция: {REACTION_EMOJI}")
        print()
        print("1. 🚀 Запустить")
        print("2. ❌ Отмена")
        
        choice = get_number_input("Выберите", 1, 2, 2)
        if choice != 1:
            return
        
        print_header("❤️ ЗАПУСК МАСС-РЕАКЦИЙ")
        
        task_count = 0
        for account in selected_accounts:
            for chat in selected_chats:
                task_key = f"{account['phone']}_{chat['id']}"
                if task_key not in reaction_tasks or reaction_tasks[task_key].done():
                    task = asyncio.create_task(
                        reaction_worker(account, chat['id'], chat['name'], api_id, api_hash, task_count)
                    )
                    reaction_tasks[task_key] = task
                    task_count += 1
                    await asyncio.sleep(0.5)
        
        print_success(f"✅ Запущено {task_count} задач реакций")
        print_info("ℹ️ Для просмотра активных реакций используйте пункт 7")
        print_info("ℹ️ Для остановки используйте пункт 6")
        
    except Exception as e:
        print_error(f"Ошибка: {e}")
    finally:
        await client.stop()
        wait_for_enter()

async def stop_reactions():
    """Остановка всех масс-реакций"""
    global reaction_active, reaction_tasks
    
    async with reaction_lock:
        if not reaction_active:
            print_info("📭 Нет активных реакций")
            wait_for_enter()
            return
        
        print_header("⏹ ОСТАНОВКА МАСС-РЕАКЦИЙ")
        
        for chat_id, accounts in reaction_active.items():
            print(f"💬 Чат ID: {chat_id}")
            for phone in list(accounts.keys()):
                print(f"   🟢 {phone}")
        
        print()
        print("1. ⏹ Остановить все")
        print("2. ❌ Отмена")
        
        choice = get_number_input("Выберите", 1, 2, 2)
        if choice == 1:
            for chat_id in list(reaction_active.keys()):
                for phone in list(reaction_active[chat_id].keys()):
                    reaction_active[chat_id][phone] = False
            
            for task_key in list(reaction_tasks.keys()):
                if not reaction_tasks[task_key].done():
                    reaction_tasks[task_key].cancel()
                del reaction_tasks[task_key]
            
            print_success("✅ Все реакции остановлены")
        
        wait_for_enter()

async def show_active_reactions():
    """Показать активные реакции"""
    async with reaction_lock:
        if not reaction_active:
            print_info("📭 Нет активных реакций")
        else:
            print_header("❤️ АКТИВНЫЕ РЕАКЦИИ")
            for chat_id, accounts in reaction_active.items():
                print(f"💬 Чат ID: {chat_id}")
                for phone, active in accounts.items():
                    status = "🟢" if active else "🔴"
                    print(f"   {status} {phone}")
            print("-" * 60)
        
        wait_for_enter()

# ===================== ГЛАВНОЕ МЕНЮ =====================

async def functions_menu(api_id, api_hash):
    """Меню функций"""
    while True:
        print_header("⚙️ МЕНЮ ФУНКЦИЙ")
        print("1. 👥 Создание групп")
        print("2. 📢 Создание каналов")
        print("3. 🤖 Создание ботов")
        print("4. 📬 Рассылка сообщений")
        print("5. ❤️ Масс-реакции (запуск)")
        print("6. ⏹ Масс-реакции (остановка)")
        print("7. 📊 Показать активные реакции")
        print("8. 🔙 Назад в главное меню")
        print("-" * 60)
        
        choice = get_number_input("Выберите действие", 1, 8)
        if not choice:
            return
        
        if choice == 1:
            await create_groups(api_id, api_hash)
        elif choice == 2:
            await create_channels(api_id, api_hash)
        elif choice == 3:
            await create_bots(api_id, api_hash)
        elif choice == 4:
            await start_mailing(api_id, api_hash)
        elif choice == 5:
            await start_reactions(api_id, api_hash)
        elif choice == 6:
            await stop_reactions()
        elif choice == 7:
            await show_active_reactions()
        elif choice == 8:
            break

async def main():
    """Главная функция"""
    try:
        config = check_api_config()
        api_id = config["api_id"]
        api_hash = config["api_hash"]
        
        while True:
            print_header("🚀 VEST SOFT - Telegram Account Manager")
            print("1. 📱 Менеджер аккаунтов")
            print("2. ⚙️ Функции (Группы/Каналы/Боты/Рассылка/Реакции)")
            print("3. ❌ Выход")
            print("-" * 60)
            
            choice = get_number_input("Выберите пункт меню", 1, 3)
            if not choice:
                continue
            
            if choice == 1:
                await account_manager(api_id, api_hash)
            elif choice == 2:
                await functions_menu(api_id, api_hash)
            elif choice == 3:
                print("\n👋 До свидания!")
                break
    
    except KeyboardInterrupt:
        print("\n\n👋 Программа завершена пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        wait_for_enter()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Программа завершена пользователем")
