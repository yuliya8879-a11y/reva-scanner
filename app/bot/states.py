"""FSM state groups for Telegram bot conversation flows."""

from aiogram.fsm.state import State, StatesGroup


class MiniScanStates(StatesGroup):
    birth_date = State()      # Q1: waiting for birth date text input
    business_area = State()   # Q2: inline keyboard
    business_age = State()    # Q3: inline keyboard
    main_pain = State()       # Q4: inline keyboard
    situation = State()       # Q5: optional text or skip
    generating = State()      # Processing state


class FullScanStates(StatesGroup):
    """FSM states for the full scan questionnaire.

    States q0-q14 map to question indices 0-14 (covering max 15 questions
    for personal scan type). State 'completing' is entered after all
    questions are answered and the questionnaire is being finalized.
    """

    q0 = State()   # Question index 0
    q1 = State()   # Question index 1
    q2 = State()   # Question index 2
    q3 = State()   # Question index 3
    q4 = State()   # Question index 4
    q5 = State()   # Question index 5
    q6 = State()   # Question index 6
    q7 = State()   # Question index 7
    q8 = State()   # Question index 8
    q9 = State()   # Question index 9
    q10 = State()  # Question index 10
    q11 = State()  # Question index 11
    q12 = State()  # Question index 12
    q13 = State()  # Question index 13
    q14 = State()  # Question index 14
    completing = State()  # All questions answered; persisting and transitioning
