import os
import re
from flask import Flask, render_template, request, session
from google import genai

app = Flask(__name__)
app.secret_key = "secret_key_lab7_agent" 


API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)


def calculator_tool(expression: str) -> str:
    """Обчислює математичний вираз та повертає результат у вигляді рядка."""
    try:
        clean_expr = re.sub(r'[^0-9\+\-\*\/\(\)\.\s]', '', expression)
        if not clean_expr.strip():
            return "Помилка: некоректний вираз для обчислення."
        result = eval(clean_expr)
        return str(result)
    except Exception as e:
        return f"Помилка обчислення: {str(e)}"


def run_agent(user_input: str, history: list):
    history_context = ""
    if history:
        history_context = "Історія попереднього діалогу:\n"
        for msg in history:
            history_context += f"- Користувач: {msg['user']}\n  Агент: {msg['agent']}\n"
        history_context += "\n"

    planner_prompt = f"""
Ти — AI-агент "Помічник студента".
Твоє завдання — проаналізувати запит користувача, враховуючи історію спілкування, та підготувати план дій.

{history_context}
Поточний запит користувача: "{user_input}"

Дай відповідь STRICTLY у такому форматі:
ПЛАН:
1. <перший крок>
2. <другий крок>
...
ПОТРІБЕН_ІНСТРУМЕНТ: Так або Ні
ВИРАЗ_ДЛЯ_КАЛЬКУЛЯТОРА: <математичний вираз, якщо потрібен калькулятор, інакше Немає>
"""
    
    res_plan = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=planner_prompt
    ).text

    plan_text = ""
    need_tool = False
    calc_expr = ""

    lines = res_plan.strip().split("\n")
    is_plan_section = False
    
    for line in lines:
        if line.startswith("ПЛАН:"):
            is_plan_section = True
            continue
        elif line.startswith("ПОТРІБЕН_ІНСТРУМЕНТ:"):
            is_plan_section = False
            if "так" in line.lower():
                need_tool = True
        elif line.startswith("ВИРАЗ_ДЛЯ_КАЛЬКУЛЯТОРА:"):
            is_plan_section = False
            calc_expr = line.replace("ВИРАЗ_ДЛЯ_КАЛЬКУЛЯТОРА:", "").strip()
        elif is_plan_section:
            plan_text += line + "\n"

    tool_used = "Не використовувався"
    tool_result = None

    if need_tool and calc_expr and calc_expr.lower() != "немає":
        tool_used = f"Calculator (вираз: {calc_expr})"
        tool_result = calculator_tool(calc_expr)

    final_prompt = f"""
Ти — AI-агент "Помічник студента".
Відповідай суворо українською мовою.

{history_context}
Поточний запит користувача: "{user_input}"
План, який ти виконав:
{plan_text}

Інформація про інструмент:
Використаний інструмент: {tool_used}
Результат інструменту: {tool_result if tool_result else "не застосовувався"}

Сформуй розгортану, приємну та вичерпну відповідь для студента на основі цих даних.
"""

    final_response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=final_prompt
    ).text

    return {
        "plan": plan_text.strip(),
        "tool_used": tool_used,
        "tool_result": tool_result,
        "response": final_response
    }


@app.route("/", methods=["GET", "POST"])
def index():
    if "history" not in session:
        session["history"] = []

    latest_result = None

    if request.method == "POST":
        user_input = request.form.get("user_input")
        action = request.form.get("action")

        if action == "clear":
            session["history"] = []
        elif user_input:
            result = run_agent(user_input, session["history"])

            current_history = session["history"]
            current_history.append({
                "user": user_input,
                "agent": result["response"]
            })
            session["history"] = current_history
            
            latest_result = result

    return render_template("index.html", history=session.get("history", []), latest=latest_result)

if __name__ == "__main__":
    app.run(debug=True, port=5002)