import os
import subprocess
import telebot
from telebot import types

# --- НАСТРОЙКИ ---
BOT_TOKEN = "BOT_TOKEN"
ADMIN_ID = 111  # Ваш Telegram ID

bot = telebot.TeleBot(BOT_TOKEN)

# Функция для выполнения команд PowerShell
def run_ps_command(command):
    try:
        # Запускаем через powershell.exe с правильной кодировкой для русской Windows
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            encoding="cp1251", # Чтобы не было иероглифов в ошибках
            check=True
        )
        return result.stdout if result.stdout else "Выполнено."
    except subprocess.CalledProcessError as e:
        return f"Ошибка выполнения:\n{e.stderr}"

# Проверка прав доступа
def is_admin(message):
    return message.from_user.id == ADMIN_ID

# Главное меню
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_list = types.KeyboardButton("📋 Список ВМ Hyper-V")
    btn_status = types.KeyboardButton("📊 Запущенные ВМ")
    markup.add(btn_list, btn_status)
    return markup

# Кнопки управления для конкретной ВМ
def get_vm_keyboard(vm_name):
    markup = types.InlineKeyboardMarkup()
    btn_start = types.InlineKeyboardButton("▶️ Включить", callback_data=f"start_{vm_name}")
    btn_stop = types.InlineKeyboardButton("⏹️ Выключить", callback_data=f"stop_{vm_name}")
    btn_reset = types.InlineKeyboardButton("🔄 Перезагрузить", callback_data=f"reset_{vm_name}")
    markup.add(btn_start, btn_stop)
    markup.add(btn_reset)
    return markup

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_admin(message): return
    bot.reply_to(message, "Бот готов к управлению Hyper-V. Запустите консоль от Админа!", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "📋 Список ВМ Hyper-V")
def list_vms(message):
    if not is_admin(message): return
    
    # Запрашиваем у Hyper-V имя и основные характеристики всех ВМ одной командой
    # Данные разделяем символом ";" для удобного парсинга в Python
    cmd = "Get-VM | ForEach-Object { $_.Name + ';' + $_.State + ';' + $_.MemoryAssigned/1MB + ';' + $_.ProcessorCount + ';' + $_.Uptime }"
    raw_output = run_ps_command(cmd)
    
    if "Ошибка" in raw_output:
        bot.send_message(message.chat.id, raw_output)
        return

    lines = [line.strip() for line in raw_output.strip().split('\n') if line.strip()]
    
    if not lines or lines == ['']:
        bot.send_message(message.chat.id, "В диспетчере Hyper-V не найдено виртуальных машин.")
        return

    bot.send_message(message.chat.id, "📊 **Список виртуальных машин и их характеристики:**", parse_mode="Markdown")
    
    for line in lines:
        try:
            # Разбираем полученную строку по разделителю ";"
            name, state, memory, cpus, uptime = line.split(';')
            
            # Переводим статус на русский для красоты
            state_ru = "🟢 Запущена" if state == "Running" else "🔴 Выключена"
            
            # Форматируем вывод аптайма (убираем миллисекунды, если они есть)
            uptime_str = uptime.split('.')[0] if uptime and uptime != "00:00:00" else "—"
            
            # Красиво собираем текст для пользователя
            info_text = (
                f"🖥️ ВМ: **{name}**\n"
                f"🔹 Статус: {state_ru}\n"
                f"🧠 Память: `{int(float(memory))} MB`\n"
                f"⚡ Процессоры: `{cpus} vCPU`\n"
                f"⏱️ Наработка: `{uptime_str}`"
            )
            
            # Отправляем карточку машины с кнопками управления
            bot.send_message(message.chat.id, info_text, reply_markup=get_vm_keyboard(name), parse_mode="Markdown")
            
        except Exception as e:
            # На случай, если какая-то строка распарсилась некорректно
            continue
@bot.message_handler(func=lambda message: message.text == "📊 Запущенные ВМ")
def list_running_vms(message):
    if not is_admin(message): return
    # Получаем список ВМ со статусом Running
    output = run_ps_command("Get-VM | Where-Object {$_.State -eq 'Running'} | Select-Object Name, State, CPUUsage, MemoryAssigned | Format-Table -HideTableHeaders")
    
    if not output.strip():
        bot.send_message(message.chat.id, "Сейчас нет запущенных машин.")
    else:
        bot.send_message(message.chat.id, f"**Запущенные ВМ (Имя, ЦП, Память):**\n```\n{output.strip()}\n```", parse_mode="Markdown")

# --- ДЕЙСТВИЯ ---

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.from_user.id != ADMIN_ID: return

    action, vm_name = call.data.split('_', 1)
    
    if action == "start":
        bot.answer_callback_query(call.id, f"Включаю {vm_name}...")
        res = run_ps_command(f'Start-VM -Name "{vm_name}"')
        bot.send_message(call.message.chat.id, f"Результат запуска {vm_name}:\n{res}")
        
    elif action == "stop":
        bot.answer_callback_query(call.id, f"Выключаю {vm_name}...")
        # Stop-VM отправляет корректный сигнал завершения работы ОС
        res = run_ps_command(f'Stop-VM -Name "{vm_name}"')
        bot.send_message(call.message.chat.id, f"Результат остановки {vm_name}:\n{res}")
        
    elif action == "reset":
        bot.answer_callback_query(call.id, f"Перезагружаю {vm_name}...")
        res = run_ps_command(f'Restart-VM -Name "{vm_name}" -Force')
        bot.send_message(call.message.chat.id, f"Результат перезагрузки {vm_name}:\n{res}")

if __name__ == "__main__":
    print("Бот для Hyper-V запущен...")
    bot.infinity_polling()
