"""Unit tests for Pydantic schema validators in app/schemas.py."""

import pytest
from pydantic import ValidationError

from app.schemas import TicketCreate


def test_valid_payload_constructs_without_error():
    t = TicketCreate(
        title="App crashes on export",
        body="The app crashes when I export to PDF.",
        customer_email="anna@example.com",
    )
    assert t.customer_email == "anna@example.com"
    assert t.title == "App crashes on export"


def test_email_normalised_to_lowercase():
    t = TicketCreate(title="T", body="B", customer_email="Anna@Example.COM")
    assert t.customer_email == "anna@example.com"


def test_email_leading_trailing_spaces_stripped_and_lowercased():
    t = TicketCreate(title="T", body="B", customer_email="  Anna@Example.COM  ")
    assert t.customer_email == "anna@example.com"


def test_email_missing_at_sign_raises_validation_error():
    with pytest.raises(ValidationError, match="Invalid email address"):
        TicketCreate(title="T", body="B", customer_email="notanemail")


def test_email_missing_domain_dot_raises_validation_error():
    with pytest.raises(ValidationError, match="Invalid email address"):
        TicketCreate(title="T", body="B", customer_email="user@nodot")


def test_empty_title_whitespace_only_raises_validation_error():
    with pytest.raises(ValidationError, match="Field must not be empty"):
        TicketCreate(title="   ", body="B", customer_email="a@b.com")


def test_empty_body_whitespace_only_raises_validation_error():
    with pytest.raises(ValidationError, match="Field must not be empty"):
        TicketCreate(title="T", body="  \n  \t  ", customer_email="a@b.com")


def test_missing_title_raises_validation_error():
    data: dict = {"body": "B", "customer_email": "a@b.com"}
    with pytest.raises(ValidationError):
        TicketCreate(**data)


def test_missing_body_raises_validation_error():
    data: dict = {"title": "T", "customer_email": "a@b.com"}
    with pytest.raises(ValidationError):
        TicketCreate(**data)
