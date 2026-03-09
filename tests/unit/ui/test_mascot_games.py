# tests/unit/ui/test_mascot_games.py
import pytest

from src.cli.ui.mascot_games import CatchGame, TypingGame, WaitingGames


def test_catch_game_init():
    game = CatchGame(width=40)
    assert game.width == 40
    assert game.score == 0


def test_catch_game_render():
    game = CatchGame(width=20)
    frame = game.render_frame()
    assert len(frame) > 0
    assert "(=^" in frame  # Mascotte présente


def test_typing_game_init():
    game = TypingGame()
    assert game.current_msg in TypingGame.MESSAGES
    assert game.pos == 0


def test_typing_game_frame():
    game = TypingGame()
    frame = game.get_frame()
    assert len(frame) > 0
    assert "▌" in frame  # Curseur présent


def test_waiting_games_manager():
    games = WaitingGames()
    assert games.console is not None
