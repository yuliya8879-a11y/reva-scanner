"""FSM state groups for Telegram bot conversation flows."""

from aiogram.fsm.state import State, StatesGroup


class MiniScanStates(StatesGroup):
    birth_date = State()      # Q1: waiting for birth date text input
    business_area = State()   # Q2: inline keyboard
    business_age = State()    # Q3: inline keyboard
    main_pain = State()       # Q4: inline keyboard
    situation = State()       # Q5: optional text or skip
    generating = State()      # Processing state
