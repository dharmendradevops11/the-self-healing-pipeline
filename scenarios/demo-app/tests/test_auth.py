from src.auth import Profile, Session, User, get_display_name, greet


def test_returns_trimmed_profile_name():
    assert get_display_name(Session(User("1", Profile("  Ada ")))) == "Ada"


def test_greets_returning_user():
    assert greet(Session(User("1", Profile("Ada")))) == "Welcome back, Ada!"


def test_first_time_user_without_profile_gets_a_default_name():
    # Fails on purpose until the bug is fixed.
    assert get_display_name(Session(User("2"))) == "there"
