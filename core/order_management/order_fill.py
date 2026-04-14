"""
OrderFill類別 - 成交記錄
記錄單筆成交的詳細資訊
"""

from datetime import datetime
from typing import Optional


class OrderFill:
    """
    成交記錄類別
    記錄每筆成交的時間、價格、數量等資訊
    """
    
    def __init__(
        self,
        order_id: str,
        fill_quantity: int,
        fill_price: float,
        commission: float = 0.0,
        tax: float = 0.0,
        fill_time: Optional[datetime] = None,
        broker_fill_id: Optional[str] = None,
    ):
        self.fill_id = f"{order_id}_{fill_quantity}_{int(fill_price)}"
        self.order_id = order_id
        self.fill_quantity = fill_quantity
        self.fill_price = fill_price
        self.commission = commission
        self.tax = tax
        self.fill_time = fill_time or datetime.now()
        self.broker_fill_id = broker_fill_id
        
        # 計算成交金額
        self.fill_amount = fill_quantity * fill_price
        self.total_cost = commission + tax
        self.net_amount = self.fill_amount - self.total_cost
        
    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "fill_amount": self.fill_amount,
            "commission": self.commission,
            "tax": self.tax,
            "total_cost": self.total_cost,
            "net_amount": self.net_amount,
            "fill_time": self.fill_time.isoformat(),
            "broker_fill_id": self.broker_fill_id,
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> 'OrderFill':
        """從字典創建實例"""
        fill = cls(
            order_id=data["order_id"],
            fill_quantity=data["fill_quantity"],
            fill_price=data["fill_price"],
            commission=data.get("commission", 0.0),
            tax=data.get("tax", 0.0),
            broker_fill_id=data.get("broker_fill_id"),
        )
        fill.fill_time = datetime.fromisoformat(data["fill_time"])
        return fill
        
    def __str__(self) -> str:
        return f"Fill({self.order_id}: {self.fill_quantity} @ {self.fill_price})"
        
    def __repr__(self) -> str:
        return f"<OrderFill {self.fill_id}>"