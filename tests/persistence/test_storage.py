"""Tests for TradingStorage class."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, select

from staarb.core.bus.events import PositionEvent, SessionEvent
from staarb.core.enums import OrderSide, PositionDirection, SessionType
from staarb.core.types import Fill, Order, Symbol, Transaction
from staarb.persistence.models import Fill as DbFill
from staarb.persistence.models import Order as DbOrder
from staarb.persistence.models import Position as DbPosition
from staarb.persistence.models import TradingSession
from staarb.persistence.models import Transaction as DbTransaction
from staarb.persistence.storage import TradingStorage
from staarb.portfolio.position import Position


class TestTradingStorage:
    """Test TradingStorage class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary SQLite database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_url = f"sqlite:///{tmp_file.name}"
            yield db_url
            # Cleanup
            Path(tmp_file.name).unlink(missing_ok=True)

    @pytest.fixture
    def storage(self, temp_db):
        """Create TradingStorage instance with temporary database."""
        return TradingStorage(temp_db)

    @pytest.fixture
    def btc_symbol(self):
        """Create a BTC symbol for testing."""
        return Symbol(
            symbol="BTCUSDT",
            baseAsset="BTC",
            quoteAsset="USDT",
            baseAssetPrecision=8,
            quoteAssetPrecision=8,
            filters=[],
        )

    @pytest.fixture
    def sample_session_event(self):
        """Create a sample session event."""
        return SessionEvent(
            session_type=SessionType.BACKTEST,
            start_time=datetime.now(UTC),
            end_time=None,
        )

    @pytest.fixture
    def sample_order(self, btc_symbol):
        """Create a sample order."""
        return Order(symbol=btc_symbol, quantity=0.1, side=OrderSide.BUY, price=50000.0, type="MARKET")

    @pytest.fixture
    def sample_fill(self, btc_symbol):
        """Create a sample fill."""
        return Fill(symbol=btc_symbol, price=50000.0, quantity=0.1, commission=0.001, commission_asset="BTC")

    @pytest.fixture
    def sample_transaction(self, sample_order, sample_fill):
        """Create a sample transaction."""
        # Use timezone-naive datetime to match SQLite storage behavior
        naive_time = datetime.now(UTC).replace(tzinfo=None)
        return Transaction(order=sample_order, fills=[sample_fill], transact_time=naive_time)

    @pytest.fixture
    def sample_position(self, btc_symbol, sample_transaction):
        """Create a sample position with transaction."""
        position = Position(symbol=btc_symbol, size=0.1)
        position.transaction_history = [sample_transaction]
        position.position_direction = PositionDirection.LONG
        position.entry_price = 50000.0
        position.entry_time = datetime.now(UTC)
        position.pnl = 0.0
        return position

    def test_init_creates_tables(self, temp_db):
        """Test that TradingStorage initialization creates database tables."""
        storage = TradingStorage(temp_db)

        # Verify engine is created
        assert storage.engine is not None

        # Verify tables exist by checking metadata
        table_names = list(SQLModel.metadata.tables.keys())
        expected_tables = ["tradingsession", "position", "transaction", "order", "fill"]

        for table in expected_tables:
            assert table in table_names

    async def test_save_session_success(self, storage, sample_session_event):
        """Test successful session start."""
        await storage.save_session(sample_session_event)

        # Verify session was stored
        assert hasattr(storage, "session")
        assert storage.session.session_id == sample_session_event.session_id
        assert storage.session.session_type == sample_session_event.session_type

        # Verify session exists in database
        with Session(storage.engine) as db_session:
            db_session_obj = db_session.get(TradingSession, sample_session_event.session_id)
            assert db_session_obj is not None
            assert db_session_obj.session_type == sample_session_event.session_type

    async def test_save_position_new_position(self, storage, sample_session_event, sample_position):
        """Test saving a new position."""
        # Start a session first
        await storage.save_session(sample_session_event)

        position_event = PositionEvent(position=sample_position)
        await storage.save_position(position_event)

        # Verify position was saved in database
        with Session(storage.engine) as db_session:
            db_position = db_session.get(DbPosition, sample_position.position_id)
            assert db_position is not None
            assert db_position.symbol == sample_position.symbol.name
            assert db_position.size == sample_position.size
            assert db_position.session_id == storage.session.session_id

    async def test_save_position_update_existing(self, storage, sample_session_event, sample_position):
        """Test updating an existing position."""
        # Start a session first
        await storage.save_session(sample_session_event)

        # Save position initially
        position_event = PositionEvent(position=sample_position)
        await storage.save_position(position_event)

        # Update position
        sample_position.size = 0.2
        sample_position.pnl = 100.0
        sample_position.is_closed = True

        # Save updated position
        updated_event = PositionEvent(position=sample_position)
        await storage.save_position(updated_event)

        # Verify position was updated
        with Session(storage.engine) as db_session:
            db_position = db_session.get(DbPosition, sample_position.position_id)
            assert db_position.size == 0.2
            assert db_position.pnl == 100.0
            assert db_position.is_closed is True

    async def test_save_position_with_transactions(self, storage, sample_session_event, btc_symbol):
        """Test saving position with multiple transactions."""
        # Start a session first
        await storage.save_session(sample_session_event)

        # Create position with multiple transactions
        position = Position(symbol=btc_symbol, size=0.1)

        # Create multiple transactions with timezone-naive datetimes
        naive_time1 = datetime.now(UTC).replace(tzinfo=None)
        naive_time2 = datetime.now(UTC).replace(tzinfo=None)

        order1 = Order(symbol=btc_symbol, quantity=0.05, side=OrderSide.BUY, price=50000.0)
        fill1 = Fill(
            symbol=btc_symbol, price=50000.0, quantity=0.05, commission=0.0005, commission_asset="BTC"
        )
        transaction1 = Transaction(order=order1, fills=[fill1], transact_time=naive_time1)

        order2 = Order(symbol=btc_symbol, quantity=0.05, side=OrderSide.BUY, price=50100.0)
        fill2 = Fill(
            symbol=btc_symbol, price=50100.0, quantity=0.05, commission=0.0005, commission_asset="BTC"
        )
        transaction2 = Transaction(order=order2, fills=[fill2], transact_time=naive_time2)

        position.transaction_history = [transaction1, transaction2]
        position.position_direction = PositionDirection.LONG

        # Save position
        position_event = PositionEvent(position=position)
        await storage.save_position(position_event)

        # Verify transactions were saved
        with Session(storage.engine) as db_session:
            db_transactions = db_session.exec(select(DbTransaction)).all()
            assert len(db_transactions) == 2

            # Verify orders were saved
            db_orders = db_session.exec(select(DbOrder)).all()
            assert len(db_orders) == 2

            # Verify fills were saved
            db_fills = db_session.exec(select(DbFill)).all()
            assert len(db_fills) == 2

    def test_add_transaction_creates_related_objects(self, storage, sample_position, sample_transaction):
        """Test that _add_transaction creates transaction, order, and fill objects."""
        # This is a unit test for the private method
        engine = storage.engine

        # Create a mock position in database
        with Session(engine) as db_session:
            db_position = DbPosition(
                id=sample_position.position_id,
                symbol=sample_position.symbol.name,
                size=sample_position.size,
                entry_price=sample_position.entry_price,
                entry_time=sample_position.entry_time,
                exit_price=sample_position.exit_price,
                exit_time=sample_position.exit_time,
                pnl=sample_position.pnl,
                is_closed=sample_position.is_closed,
                session_id="test_session",
            )
            db_session.add(db_position)
            db_session.commit()
            db_session.refresh(db_position)

            # Call _add_transaction
            storage._add_transaction(sample_transaction, db_position, db_session)
            db_session.commit()

            # Verify transaction was created
            db_transaction = db_session.exec(
                select(DbTransaction).filter_by(id=sample_transaction.id)
            ).first()
            assert db_transaction is not None
            assert db_transaction.timestamp == sample_transaction.transact_time

            # Verify order was created
            db_order = db_session.exec(select(DbOrder).filter_by(transaction_id=db_transaction.id)).first()
            assert db_order is not None
            assert db_order.symbol == sample_transaction.order.symbol.name
            assert db_order.quantity == sample_transaction.order.quantity
            assert db_order.side == sample_transaction.order.side.value

            # Verify fill was created
            db_fill = db_session.exec(select(DbFill).filter_by(transaction_id=db_transaction.id)).first()
            assert db_fill is not None
            assert db_fill.symbol == sample_transaction.fills[0].symbol.name
            assert db_fill.price == sample_transaction.fills[0].price
            assert db_fill.quantity == sample_transaction.fills[0].quantity

    async def test_save_position_marks_transactions_as_saved(
        self, storage, sample_session_event, sample_position
    ):
        """Test that saving position marks transactions as saved."""
        # Start a session first
        await storage.save_session(sample_session_event)

        # Mock the position methods
        with (
            patch.object(
                sample_position, "get_unsaved_transactions", return_value=sample_position.transaction_history
            ) as mock_get_unsaved,
            patch.object(sample_position, "mark_transactions_as_saved") as mock_mark_saved,
        ):
            position_event = PositionEvent(position=sample_position)
            await storage.save_position(position_event)

            # Verify methods were called
            mock_get_unsaved.assert_called_once()
            mock_mark_saved.assert_called_once_with(len(sample_position.transaction_history))

    def test_storage_with_different_database_url(self):
        """Test TradingStorage with different database URL."""
        custom_url = "sqlite:///custom_test.db"
        storage = TradingStorage(custom_url)

        assert str(storage.engine.url) == custom_url

        # Cleanup
        Path("custom_test.db").unlink(missing_ok=True)

    def test_storage_default_database_url(self):
        """Test TradingStorage with default database URL."""
        storage = TradingStorage()

        assert "sqlite:///trading_data.db" in str(storage.engine.url)

    async def test_save_position_without_session_raises_error(self, storage, sample_position):
        """Test that saving position without starting session first raises error."""
        position_event = PositionEvent(position=sample_position)

        # This should raise an AttributeError because storage.session is not set
        with pytest.raises(AttributeError):
            await storage.save_position(position_event)

    async def test_multiple_sessions_workflow(self, storage):
        """Test workflow with multiple sessions."""
        # Create multiple sessions
        session1 = SessionEvent(
            session_type=SessionType.BACKTEST, start_time=datetime.now(UTC), session_id="session_1"
        )
        session2 = SessionEvent(
            session_type=SessionType.LIVE, start_time=datetime.now(UTC), session_id="session_2"
        )

        # Start first session
        await storage.save_session(session1)
        assert storage.session.session_id == "session_1"

        # Start second session (should overwrite)
        await storage.save_session(session2)
        assert storage.session.session_id == "session_2"

        # Verify both sessions exist in database
        with Session(storage.engine) as db_session:
            db_session1 = db_session.get(TradingSession, "session_1")
            db_session2 = db_session.get(TradingSession, "session_2")

            assert db_session1 is not None
            assert db_session2 is not None
            assert db_session1.session_type == SessionType.BACKTEST
            assert db_session2.session_type == SessionType.LIVE

    async def test_transaction_with_multiple_fills(self, storage, sample_session_event, btc_symbol):
        """Test saving transaction with multiple fills."""
        # Start a session first
        await storage.save_session(sample_session_event)

        # Create position
        position = Position(symbol=btc_symbol, size=0.1)

        # Create transaction with multiple fills (timezone-naive datetime)
        naive_time = datetime.now(UTC).replace(tzinfo=None)
        order = Order(symbol=btc_symbol, quantity=0.1, side=OrderSide.BUY, price=50000.0)
        fill1 = Fill(
            symbol=btc_symbol, price=50000.0, quantity=0.05, commission=0.0005, commission_asset="BTC"
        )
        fill2 = Fill(
            symbol=btc_symbol, price=50050.0, quantity=0.05, commission=0.0005, commission_asset="BTC"
        )
        transaction = Transaction(order=order, fills=[fill1, fill2], transact_time=naive_time)

        position.transaction_history = [transaction]
        position.position_direction = PositionDirection.LONG

        # Save position
        position_event = PositionEvent(position=position)
        await storage.save_position(position_event)

        # Verify multiple fills were saved
        with Session(storage.engine) as db_session:
            db_fills = db_session.exec(select(DbFill)).all()
            assert len(db_fills) == 2

            # Verify fill details
            fill_prices = [fill.price for fill in db_fills]
            assert 50000.0 in fill_prices
            assert 50050.0 in fill_prices

    async def test_position_relationship_with_session(self, storage, sample_session_event, sample_position):
        """Test that position is correctly linked to session."""
        # Start a session first
        await storage.save_session(sample_session_event)

        # Save position
        position_event = PositionEvent(position=sample_position)
        await storage.save_position(position_event)

        # Verify relationship in database
        with Session(storage.engine) as db_session:
            db_session_obj = db_session.get(TradingSession, sample_session_event.session_id)
            assert db_session_obj is not None

            # Check that position is linked to session
            assert len(db_session_obj.positions) == 1
            assert db_session_obj.positions[0].id == sample_position.position_id
