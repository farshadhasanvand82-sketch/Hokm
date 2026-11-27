import random
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

SUITS = ["hearts", "clubs", "diamonds", "spades"]
SUIT_META = {
    "hearts": {"symbol": "♥", "fa": "دل", "color": (0.84, 0.16, 0.22, 1)},
    "clubs": {"symbol": "♣", "fa": "گشنیز", "color": (0.10, 0.12, 0.14, 1)},
    "diamonds": {"symbol": "♦", "fa": "خشت", "color": (0.84, 0.16, 0.22, 1)},
    "spades": {"symbol": "♠", "fa": "پیک", "color": (0.10, 0.12, 0.14, 1)},
}

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUE = {r: idx + 2 for idx, r in enumerate(RANKS)}

SEATS = ["user", "right", "partner", "left"]
SEAT_NAMES = {
    "user": "شما",
    "right": "حریف راست",
    "partner": "یار شما",
    "left": "حریف چپ",
}


def team_of(seat: str) -> str:
    return "us" if seat in ("user", "partner") else "them"


def create_deck() -> list[dict]:
    deck = [
        {"id": f"{rank}-{suit}", "suit": suit, "rank": rank, "value": RANK_VALUE[rank]}
        for suit in SUITS
        for rank in RANKS
    ]
    random.shuffle(deck)
    return deck


def choose_hokm_for_ai(five_cards: list[dict]) -> str:
    weights = {s: 0 for s in SUITS}
    counts = {s: 0 for s in SUITS}
    for card in five_cards:
        s = card["suit"]
        counts[s] += 1
        weights[s] += card["value"] + counts[s] * 4
    return max(SUITS, key=lambda s: weights[s])


def get_playable_cards(hand: list[dict], lead_suit: str | None) -> list[dict]:
    if not lead_suit:
        return hand
    matching = [c for c in hand if c["suit"] == lead_suit]
    return matching if matching else hand


def card_strength(card: dict, lead_suit: str | None, hokm_suit: str | None) -> int:
    if card["suit"] == hokm_suit:
        return 100 + card["value"]
    if card["suit"] == lead_suit:
        return 50 + card["value"]
    return card["value"]


def choose_card_for_ai(
    hand: list[dict],
    lead_suit: str | None,
    hokm_suit: str | None,
    current_trick: list[dict],
    seat: str,
) -> dict:
    playable = get_playable_cards(hand, lead_suit)
    if len(playable) == 1:
        return playable[0]

    if not current_trick:
        non_hokm_high = sorted(
            [c for c in playable if c["suit"] != hokm_suit],
            key=lambda c: c["value"],
            reverse=True,
        )
        if non_hokm_high and non_hokm_high[0]["value"] >= 12:
            return non_hokm_high[0]
        return min(playable, key=lambda c: c["value"])

    best_entry = max(
        current_trick, key=lambda item: card_strength(item["card"], lead_suit, hokm_suit)
    )
    best_score = card_strength(best_entry["card"], lead_suit, hokm_suit)

    if team_of(best_entry["seat"]) == team_of(seat):
        return min(playable, key=lambda c: c["value"])

    winners = [c for c in playable if card_strength(c, lead_suit, hokm_suit) > best_score]
    if winners:
        non_hokm_winners = [c for c in winners if c["suit"] != hokm_suit]
        pool = non_hokm_winners if non_hokm_winners else winners
        return min(pool, key=lambda c: card_strength(c, lead_suit, hokm_suit))

    return min(playable, key=lambda c: c["value"])


class CardButton(Button):
    def __init__(self, card: dict, playable: bool = False, on_card_select=None, **kwargs):
        meta = SUIT_META[card["suit"]]
        super().__init__(
            text=f"{card['rank']}\n{meta['symbol']}",
            font_size="18sp",
            bold=True,
            color=meta["color"],
            background_normal="",
            background_disabled_normal="",
            background_color=(1, 1, 1, 1) if playable else (0.85, 0.87, 0.89, 0.75),
            disabled=not playable,
            **kwargs,
        )
        self.card = card
        self.on_card_select = on_card_select

    def on_release(self):
        if not self.disabled and callable(self.on_card_select):
            self.on_card_select(self.card)


class FeltBox(BoxLayout):
    def __init__(self, bg_color=(0.09, 0.36, 0.24, 1), **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_col = Color(*bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[16])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


class HokmAndroidLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=8, spacing=8, **kwargs)
        with self.canvas.before:
            Color(0.05, 0.12, 0.09, 1)
            self._root_bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_root, size=self._sync_root)

        self.target_score = 7
        self.score = {"us": 0, "them": 0}
        self.tricks = {"us": 0, "them": 0}
        self.hakem = "user"
        self.hokm: str | None = None
        self.phase = "CHOOSING_HOKM"
        self.deck: list[dict] = []
        self.hands = {s: [] for s in SEATS}
        self.lead_suit: str | None = None
        self.current_trick: list[dict] = []
        self.turn = "user"
        self.busy = False

        self._build_ui()
        self.start_new_match()

    def _sync_root(self, *_):
        self._root_bg.pos = self.pos
        self._root_bg.size = self.size

    def _build_ui(self):
        top_bar = FeltBox(
            bg_color=(0.08, 0.22, 0.16, 1),
            orientation="horizontal",
            size_hint_y=None,
            height=62,
            padding=8,
            spacing=6,
        )

        self.lbl_score = Label(
            text="ما: 0 | حریف: 0",
            font_size="14sp",
            bold=True,
            color=(0.95, 0.78, 0.37, 1),
        )
        self.lbl_hokm = Label(
            text="حکم: —", font_size="14sp", bold=True, color=(1, 1, 1, 1)
        )
        self.lbl_tricks = Label(
            text="تیک: 0-0", font_size="13sp", color=(0.82, 0.92, 0.87, 1)
        )

        btn_reset = Button(
            text="شروع مجدد",
            size_hint_x=None,
            width=96,
            font_size="12sp",
            bold=True,
            background_normal="",
            background_color=(0.18, 0.45, 0.33, 1),
        )
        btn_reset.bind(on_release=lambda *_: self.start_new_match())

        btn_rules = Button(
            text="قوانین",
            size_hint_x=None,
            width=72,
            font_size="12sp",
            bold=True,
            background_normal="",
            background_color=(0.95, 0.78, 0.37, 1),
            color=(0.08, 0.08, 0.08, 1),
        )
        btn_rules.bind(on_release=lambda *_: self.show_rules())

        top_bar.add_widget(self.lbl_score)
        top_bar.add_widget(self.lbl_hokm)
        top_bar.add_widget(self.lbl_tricks)
        top_bar.add_widget(btn_rules)
        top_bar.add_widget(btn_reset)
        self.add_widget(top_bar)

        table = FeltBox(
            bg_color=(0.09, 0.36, 0.24, 1),
            orientation="vertical",
            padding=10,
            spacing=8,
        )

        opponents_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=44, spacing=6
        )
        self.lbl_partner = Label(text="یار: 13", font_size="13sp", bold=True)
        self.lbl_left = Label(text="چپ: 13", font_size="13sp", bold=True)
        self.lbl_right = Label(text="راست: 13", font_size="13sp", bold=True)
        opponents_row.add_widget(self.lbl_left)
        opponents_row.add_widget(self.lbl_partner)
        opponents_row.add_widget(self.lbl_right)
        table.add_widget(opponents_row)

        self.lbl_status = Label(
            text="در حال آماده‌سازی...",
            size_hint_y=None,
            height=34,
            font_size="14sp",
            bold=True,
            color=(0.98, 0.92, 0.65, 1),
        )
        table.add_widget(self.lbl_status)

        self.trick_box = GridLayout(cols=4, spacing=8, size_hint_y=None, height=118)
        table.add_widget(self.trick_box)

        self.hokm_selector_box = BoxLayout(
            orientation="horizontal", spacing=8, size_hint_y=None, height=54
        )
        for suit in SUITS:
            meta = SUIT_META[suit]
            b = Button(
                text=f"{meta['symbol']} {meta['fa']}",
                font_size="15sp",
                bold=True,
                color=meta["color"],
                background_normal="",
                background_color=(1, 1, 1, 1),
            )
            b.bind(on_release=lambda _btn, s=suit: self.apply_hokm_choice(s))
            self.hokm_selector_box.add_widget(b)
        table.add_widget(self.hokm_selector_box)

        table.add_widget(Widget())

        self.lbl_user = Label(
            text="دست شما (13 کارت)",
            size_hint_y=None,
            height=28,
            font_size="14sp",
            bold=True,
            color=(0.95, 0.78, 0.37, 1),
        )
        table.add_widget(self.lbl_user)

        scroll = ScrollView(
            size_hint_y=None, height=122, do_scroll_x=True, do_scroll_y=False
        )
        self.user_hand_box = BoxLayout(
            orientation="horizontal", spacing=6, size_hint_x=None
        )
        self.user_hand_box.bind(minimum_width=self.user_hand_box.setter("width"))
        scroll.add_widget(self.user_hand_box)
        table.add_widget(scroll)

        self.add_widget(table)

    def sort_hand(self, cards: list[dict]) -> list[dict]:
        suit_order = {"spades": 0, "hearts": 1, "clubs": 2, "diamonds": 3}
        return sorted(
            cards,
            key=lambda c: (
                0 if (self.hokm and c["suit"] == self.hokm) else 1,
                suit_order[c["suit"]],
                -c["value"],
            ),
        )

    def start_new_match(self):
        self.score = {"us": 0, "them": 0}
        self.hakem = random.choice(SEATS)
        self.start_round()

    def start_round(self):
        self.tricks = {"us": 0, "them": 0}
        self.hokm = None
        self.lead_suit = None
        self.current_trick = []
        self.busy = False
        self.phase = "CHOOSING_HOKM"

        deck = create_deck()
        self.hands = {
            "user": deck[0:5],
            "right": deck[5:10],
            "partner": deck[10:15],
            "left": deck[15:20],
        }
        self.deck = deck[20:]

        self.hokm_selector_box.disabled = self.hakem != "user"
        self.hokm_selector_box.opacity = 1 if self.hakem == "user" else 0
        self.render_all()

        if self.hakem == "user":
            self.set_status("شما حاکم هستید! ۵ برگ اول را ببینید و حکم را انتخاب کنید.")
        else:
            self.set_status(f"{SEAT_NAMES[self.hakem]} در حال انتخاب حکم است...")
            Clock.schedule_once(lambda _dt: self._ai_choose_hokm(), 0.8)

    def _ai_choose_hokm(self):
        chosen = choose_hokm_for_ai(self.hands[self.hakem])
        self.apply_hokm_choice(chosen)

    def apply_hokm_choice(self, suit: str):
        self.hokm = suit
        self.hokm_selector_box.disabled = True
        self.hokm_selector_box.opacity = 0

        for seat in SEATS:
            extra = self.deck[:8]
            self.deck = self.deck[8:]
            self.hands[seat] = self.sort_hand(self.hands[seat] + extra)

        self.phase = "PLAYING"
        self.turn = self.hakem
        self.lead_suit = None
        self.current_trick = []
        self.render_all()

        meta = SUIT_META[suit]
        self.set_status(
            f"حکم «{meta['fa']} {meta['symbol']}» شد — نوبت {SEAT_NAMES[self.turn]}"
        )

        if self.turn != "user":
            self.schedule_ai_turn()

    def on_user_card_select(self, card: dict):
        if self.phase != "PLAYING" or self.busy or self.turn != "user":
            return
        playable = get_playable_cards(self.hands["user"], self.lead_suit)
        if not any(c["id"] == card["id"] for c in playable):
            return
        self.play_card("user", card)

    def play_card(self, seat: str, card: dict):
        self.hands[seat] = [c for c in self.hands[seat] if c["id"] != card["id"]]
        if not self.current_trick:
            self.lead_suit = card["suit"]
        self.current_trick.append({"seat": seat, "card": card})
        self.render_all()

        if len(self.current_trick) < 4:
            next_idx = (SEATS.index(seat) + 1) % len(SEATS)
            self.turn = SEATS[next_idx]
            self.set_status(f"نوبت {SEAT_NAMES[self.turn]}...")
            if self.turn != "user":
                self.schedule_ai_turn()
        else:
            self.busy = True
            Clock.schedule_once(lambda _dt: self.resolve_trick(), 0.85)

    def resolve_trick(self):
        winner_entry = max(
            self.current_trick,
            key=lambda item: card_strength(item["card"], self.lead_suit, self.hokm),
        )
        winner_seat = winner_entry["seat"]
        self.tricks[team_of(winner_seat)] += 1
        self.set_status(f"تیک را {SEAT_NAMES[winner_seat]} برد!")

        def after_clear(_dt):
            self.current_trick = []
            self.lead_suit = None
            self.busy = False

            if (
                self.tricks["us"] >= 7
                or self.tricks["them"] >= 7
                or len(self.hands["user"]) == 0
            ):
                self.finish_round()
                return

            self.turn = winner_seat
            self.render_all()
            self.set_status(f"تیک جدید — شروع با {SEAT_NAMES[self.turn]}")
            if self.turn != "user":
                self.schedule_ai_turn()

        Clock.schedule_once(after_clear, 0.65)

    def finish_round(self):
        self.phase = "ROUND_OVER"
        us_won = self.tricks["us"] > self.tricks["them"]
        winner_team = "us" if us_won else "them"
        loser_team = "them" if us_won else "us"

        is_koot = self.tricks[loser_team] == 0
        self.score[winner_team] += 2 if is_koot else 1

        if team_of(self.hakem) != winner_team:
            hakem_idx = SEATS.index(self.hakem)
            self.hakem = SEATS[(hakem_idx + 1) % len(SEATS)]

        self.render_all()
        winner_label = "تیم شما" if winner_team == "us" else "تیم حریف"
        koot_txt = " (کوت! +۲)" if is_koot else " (+۱)"

        if self.score[winner_team] >= self.target_score:
            self.phase = "MATCH_OVER"
            self._open_info_popup(
                "پایان بازی",
                f"{winner_label} با {self.score[winner_team]} امتیاز برنده شد!",
                on_close=self.start_new_match,
            )
        else:
            self._open_info_popup(
                "پایان دست",
                f"برنده دست: {winner_label}{koot_txt}\nتیک‌ها: شما {self.tricks['us']} - حریف {self.tricks['them']}\nامتیاز کل: شما {self.score['us']} - حریف {self.score['them']}",
                on_close=self.start_round,
            )

    def _open_info_popup(self, title: str, message: str, on_close=None):
        content = BoxLayout(orientation="vertical", padding=12, spacing=10)
        content.add_widget(Label(text=message, font_size="14sp"))
        btn_ok = Button(
            text="ادامه", size_hint_y=None, height=44, font_size="14sp", bold=True
        )
        content.add_widget(btn_ok)
        popup = Popup(
            title=title, content=content, size_hint=(0.82, 0.45), auto_dismiss=False
        )

        def _done(*_):
            popup.dismiss()
            if callable(on_close):
                on_close()

        btn_ok.bind(on_release=_done)
        popup.open()

    def schedule_ai_turn(self):
        self.busy = True

        def run_ai(_dt):
            seat = self.turn
            card = choose_card_for_ai(
                self.hands[seat], self.lead_suit, self.hokm, self.current_trick, seat
            )
            self.busy = False
            self.play_card(seat, card)

        Clock.schedule_once(run_ai, 0.55)

    def render_all(self):
        self.lbl_score.text = f"ما: {self.score['us']} | حریف: {self.score['them']}"
        self.lbl_tricks.text = f"تیک: {self.tricks['us']}-{self.tricks['them']}"
        if self.hokm:
            m = SUIT_META[self.hokm]
            self.lbl_hokm.text = f"حکم: {m['symbol']} {m['fa']}"
        else:
            self.lbl_hokm.text = f"حاکم: {SEAT_NAMES[self.hakem]}"

        self.lbl_partner.text = f"یار: {len(self.hands['partner'])}"
        self.lbl_left.text = f"چپ: {len(self.hands['left'])}"
        self.lbl_right.text = f"راست: {len(self.hands['right'])}"
        self.lbl_user.text = (
            f"شما ({len(self.hands['user'])} کارت) — حاکم: {SEAT_NAMES[self.hakem]}"
        )

        self.user_hand_box.clear_widgets()
        playable_ids = {
            c["id"] for c in get_playable_cards(self.hands["user"], self.lead_suit)
        }
        for card in self.hands["user"]:
            can_play = (
                self.phase == "PLAYING"
                and not self.busy
                and self.turn == "user"
                and card["id"] in playable_ids
            )
            btn = CardButton(
                card=card,
                playable=can_play,
                on_card_select=self.on_user_card_select if can_play else None,
                size_hint=(None, None),
                size=(72, 108),
            )
            self.user_hand_box.add_widget(btn)

        self.trick_box.clear_widgets()
        for entry in self.current_trick:
            slot = BoxLayout(orientation="vertical", spacing=2)
            slot.add_widget(
                Label(
                    text=SEAT_NAMES[entry["seat"]],
                    size_hint_y=None,
                    height=20,
                    font_size="11sp",
                    color=(0.95, 0.78, 0.37, 1),
                )
            )
            slot.add_widget(CardButton(card=entry["card"], playable=False))
            self.trick_box.add_widget(slot)

    def set_status(self, text: str):
        self.lbl_status.text = text

    def show_rules(self):
        rules_text = (
            "قوانین حکم ایرانی:\n"
            "• ۴ نفر در دو تیم دو نفره (شما و یار در برابر چپ و راست).\n"
            "• حاکم ۵ برگ اول را می‌بیند و حکم را مشخص می‌کند؛ سپس هر نفر ۱۳ کارته می‌شود.\n"
            "• پیروی از خال زمین در صورت داشتن آن اجباری است.\n"
            "• بردن ۷ تیک = +۱ امتیاز (کوت شدن حریف = +۲ امتیاز).\n"
            "• اولین تیم با ۷ امتیاز برنده بازی است."
        )
        self._open_info_popup("قوانین حکم", rules_text)


class HokmAndroidApp(App):
    def build(self):
        self.title = "حکم ایرانی"
        Window.clearcolor = (0.05, 0.12, 0.09, 1)
        return HokmAndroidLayout()


if __name__ == "__main__":
    HokmAndroidApp().run()
