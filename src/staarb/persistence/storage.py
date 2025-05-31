from sqlmodel import Session, SQLModel, create_engine

from staarb.core.bus.events import PositionEvent, SessionEvent
from staarb.core.types import Transaction as TransactionType
from staarb.persistence.models import Fill, Order, Position, TradingSession, Transaction


class TradingStorage:
    """
    A class to manage the storage of trading data.
    """

    def __init__(self, database_url: str = "sqlite:///trading_data.db"):
        """
        Initializes the TradingStorage with a specified storage path.

        :param storage_path: The path where trading data will be stored.
        """
        self.engine = create_engine(database_url)
        SQLModel.metadata.create_all(self.engine)

    async def save_session(self, session: SessionEvent) -> None:
        """
        Saves a trading session to the storage.

        :param session: The trading session to save.
        """
        # Implementation for saving the session
        persist_session = TradingSession(
            session_id=session.session_id,
            session_type=session.session_type,
            start_time=session.start_time,
            end_time=session.end_time,
        )
        with Session(self.engine) as db_session:
            db_session.add(persist_session)
            db_session.commit()
            db_session.refresh(persist_session)
        self.session = persist_session

    def _add_transaction(self, transaction: TransactionType, position: Position, db_session: Session) -> None:
        """
        Saves a transaction to the storage.

        :param transaction: The transaction to save.
        """
        # Implementation for saving the transaction
        saved_transaction = Transaction(
            id=transaction.id, timestamp=transaction.transact_time, position=position
        )
        order = Order(
            symbol=transaction.order.symbol.name,
            quantity=transaction.order.quantity,
            side=transaction.order.side.value,
            price=transaction.order.price,
            side_effect=transaction.order.side_effect,
            type=transaction.order.type,
            time_in_force=transaction.order.time_in_force,
            transaction=saved_transaction,
        )
        transaction_fills = [
            Fill(
                symbol=fill.symbol.name,
                price=fill.price,
                quantity=fill.quantity,
                commission=fill.commission,
                commission_asset=fill.commission_asset,
                transaction=saved_transaction,
            )
            for fill in transaction.fills
        ]
        db_session.add(saved_transaction)
        db_session.add(order)
        db_session.add_all(transaction_fills)

    async def save_position(self, position_event: PositionEvent) -> None:
        """
        Saves a position to the storage.

        :param position_event: The position event containing the position to save.
        """
        position = position_event.position
        with Session(self.engine) as db_session:
            existing_position = db_session.get(Position, position.position_id)
            if existing_position:
                # Update existing position
                existing_position.size = position.size
                existing_position.entry_price = position.entry_price
                existing_position.entry_time = position.entry_time
                existing_position.exit_time = position.exit_time
                existing_position.exit_price = position.exit_price
                existing_position.pnl = position.pnl
                existing_position.is_closed = position.is_closed
                persist_position = existing_position
            else:
                # Add new position
                persist_position = Position(
                    id=position.position_id,
                    symbol=position.symbol.name,
                    size=position.size,
                    entry_price=position.entry_price,
                    entry_time=position.entry_time,
                    exit_time=position.exit_time,
                    exit_price=position.exit_price,
                    pnl=position.pnl,
                    is_closed=position.is_closed,
                    session_id=self.session.session_id,
                )
                db_session.add(persist_position)
            unsaved_transactions = position.get_unsaved_transactions()
            for transaction in unsaved_transactions:
                self._add_transaction(transaction, persist_position, db_session)
            position.mark_transactions_as_saved(len(unsaved_transactions))
            db_session.commit()
