"""
Order類別 - 委託單核心資料結構
定義委託單的狀態機和生命週期
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid


class OrderStatus(Enum):
    """委託單狀態枚舉"""
    PENDING = "pending"           # 等待提交
    SUBMITTED = "submitted"       # 已提交到券商
    PARTIAL_FILLED = "partial"    # 部分成交
    FILLED = "filled"             # 完全成交
    CANCELLED = "cancelled"       # 已取消
    REJECTED = "rejected"         # 被拒絕
    EXPIRED = "expired"           # 已過期


class OrderType(Enum):
    """委託單類型枚舉"""
    LIMIT = "limit"      # 限價單
    MARKET = "market"    # 市價單
    STOP = "stop"        # 停損單
    STOP_LIMIT = "stop_limit"  # 停損限價單


class OrderSide(Enum):
    """買賣方向枚舉"""
    BUY = "buy"
    SELL = "sell"


class Order:
    """
    委託單類別 - 管理單一委託單的完整生命週期
    
    狀態轉換圖:
    PENDING → SUBMITTED → PARTIAL_FILLED → FILLED
    PENDING → SUBMITTED → CANCELLED
    PENDING → SUBMITTED → REJECTED
    PENDING → SUBMITTED → EXPIRED
    """
    
    def __init__(
        self,
        contract: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.LIMIT,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "DAY",
        strategy: str = "",
        reason: str = "",
        parent_order_id: Optional[str] = None,
    ):
        # 基本資訊
        self.order_id = str(uuid.uuid4())[:8]  # 簡短ID方便顯示
        self.contract = contract
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.price = price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        
        # 狀態追蹤
        self.status = OrderStatus.PENDING
        self.filled_quantity = 0
        self.avg_fill_price = 0.0
        self.commission = 0.0
        self.tax = 0.0
        
        # 時間戳記
        self.created_time = datetime.now()
        self.submitted_time: Optional[datetime] = None
        self.first_fill_time: Optional[datetime] = None
        self.last_fill_time: Optional[datetime] = None
        self.cancelled_time: Optional[datetime] = None
        self.expired_time: Optional[datetime] = None
        
        # 成交記錄
        self.fills: List[Dict[str, Any]] = []
        
        # 關聯資訊
        self.strategy = strategy
        self.reason = reason
        self.parent_order_id = parent_order_id
        self.broker_order_id: Optional[str] = None  # 券商委託單ID
        self.error_message: Optional[str] = None
        
        # 執行品質指標
        self.slippage = 0.0  # 滑價（成交價-委託價）
        self.fill_duration: Optional[float] = None  # 成交耗時（秒）
        
    def submit(self, broker_order_id: Optional[str] = None) -> bool:
        """提交委託單到券商"""
        if self.status != OrderStatus.PENDING:
            return False
            
        self.status = OrderStatus.SUBMITTED
        self.submitted_time = datetime.now()
        self.broker_order_id = broker_order_id
        return True
        
    def add_fill(self, fill_quantity: int, fill_price: float, 
                 commission: float = 0.0, tax: float = 0.0) -> bool:
        """添加成交記錄"""
        if self.status in [OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
            return False
            
        fill_time = datetime.now()
        fill_record = {
            "time": fill_time,
            "quantity": fill_quantity,
            "price": fill_price,
            "commission": commission,
            "tax": tax,
        }
        self.fills.append(fill_record)
        
        # 更新成交統計
        total_filled = self.filled_quantity + fill_quantity
        self.avg_fill_price = (
            (self.avg_fill_price * self.filled_quantity + fill_price * fill_quantity)
            / total_filled if total_filled > 0 else 0
        )
        self.filled_quantity = total_filled
        self.commission += commission
        self.tax += tax
        
        # 更新時間戳記
        if not self.first_fill_time:
            self.first_fill_time = fill_time
        self.last_fill_time = fill_time
        
        # 更新狀態
        if self.filled_quantity == self.quantity:
            self.status = OrderStatus.FILLED
            if self.first_fill_time:
                self.fill_duration = (fill_time - self.first_fill_time).total_seconds()
            # 計算滑價（限價單才有意義）
            if self.order_type == OrderType.LIMIT and self.price:
                self.slippage = fill_price - self.price
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIAL_FILLED
            
        return True
        
    def cancel(self) -> bool:
        """取消委託單"""
        if self.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]:
            return False
            
        self.status = OrderStatus.CANCELLED
        self.cancelled_time = datetime.now()
        return True
        
    def reject(self, error_message: str) -> bool:
        """拒絕委託單"""
        if self.status != OrderStatus.PENDING:
            return False
            
        self.status = OrderStatus.REJECTED
        self.error_message = error_message
        return True
        
    def expire(self) -> bool:
        """委託單過期"""
        if self.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            return False
            
        self.status = OrderStatus.EXPIRED
        self.expired_time = datetime.now()
        return True
        
    def is_active(self) -> bool:
        """檢查委託單是否仍活躍（可成交）"""
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIAL_FILLED,
        ]
        
    def is_completed(self) -> bool:
        """檢查委託單是否已完成（成交/取消/拒絕/過期）"""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        ]
        
    def get_remaining_quantity(self) -> int:
        """取得未成交數量"""
        return self.quantity - self.filled_quantity
        
    def get_status_display(self) -> str:
        """取得狀態顯示文字"""
        status_map = {
            OrderStatus.PENDING: "等待提交",
            OrderStatus.SUBMITTED: "委託中",
            OrderStatus.PARTIAL_FILLED: "部分成交",
            OrderStatus.FILLED: "已成交",
            OrderStatus.CANCELLED: "已取消",
            OrderStatus.REJECTED: "已拒絕",
            OrderStatus.EXPIRED: "已過期",
        }
        return status_map.get(self.status, str(self.status.value))
        
    def get_side_display(self) -> str:
        """取得買賣方向顯示文字"""
        return "買進" if self.side == OrderSide.BUY else "賣出"
        
    def get_type_display(self) -> str:
        """取得委託單類型顯示文字"""
        type_map = {
            OrderType.LIMIT: "限價",
            OrderType.MARKET: "市價",
            OrderType.STOP: "停損",
            OrderType.STOP_LIMIT: "停損限價",
        }
        return type_map.get(self.order_type, str(self.order_type.value))
        
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式（用於序列化）"""
        return {
            "order_id": self.order_id,
            "contract": self.contract,
            "side": self.side.value,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "order_type": self.order_type.value,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "avg_fill_price": self.avg_fill_price,
            "commission": self.commission,
            "tax": self.tax,
            "created_time": self.created_time.isoformat() if self.created_time else None,
            "submitted_time": self.submitted_time.isoformat() if self.submitted_time else None,
            "first_fill_time": self.first_fill_time.isoformat() if self.first_fill_time else None,
            "last_fill_time": self.last_fill_time.isoformat() if self.last_fill_time else None,
            "strategy": self.strategy,
            "reason": self.reason,
            "broker_order_id": self.broker_order_id,
            "error_message": self.error_message,
            "slippage": self.slippage,
            "fill_duration": self.fill_duration,
            "fills": [
                {
                    "time": fill["time"].isoformat(),
                    "quantity": fill["quantity"],
                    "price": fill["price"],
                    "commission": fill["commission"],
                    "tax": fill["tax"],
                }
                for fill in self.fills
            ],
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Order':
        """從字典創建Order實例"""
        # 創建基本Order
        order = cls(
            contract=data["contract"],
            side=OrderSide(data["side"]),
            quantity=data["quantity"],
            order_type=OrderType(data["order_type"]),
            price=data["price"],
            stop_price=data.get("stop_price"),
            time_in_force=data.get("time_in_force", "DAY"),
            strategy=data.get("strategy", ""),
            reason=data.get("reason", ""),
        )
        
        # 還原狀態
        order.order_id = data["order_id"]
        order.status = OrderStatus(data["status"])
        order.filled_quantity = data["filled_quantity"]
        order.avg_fill_price = data["avg_fill_price"]
        order.commission = data["commission"]
        order.tax = data["tax"]
        
        # 還原時間戳記
        if data["created_time"]:
            order.created_time = datetime.fromisoformat(data["created_time"])
        if data["submitted_time"]:
            order.submitted_time = datetime.fromisoformat(data["submitted_time"])
        if data["first_fill_time"]:
            order.first_fill_time = datetime.fromisoformat(data["first_fill_time"])
        if data["last_fill_time"]:
            order.last_fill_time = datetime.fromisoformat(data["last_fill_time"])
            
        # 還原其他欄位
        order.broker_order_id = data.get("broker_order_id")
        order.error_message = data.get("error_message")
        order.slippage = data.get("slippage", 0.0)
        order.fill_duration = data.get("fill_duration")
        
        # 還原成交記錄（簡化處理）
        order.fills = []
        for fill_data in data.get("fills", []):
            fill = {
                "time": datetime.fromisoformat(fill_data["time"]),
                "quantity": fill_data["quantity"],
                "price": fill_data["price"],
                "commission": fill_data["commission"],
                "tax": fill_data["tax"],
            }
            order.fills.append(fill)
            
        return order
        
    def __str__(self) -> str:
        """字串表示"""
        return f"Order({self.order_id}: {self.contract} {self.get_side_display()} {self.quantity} @ {self.price or 'MKT'} - {self.get_status_display()})"
        
    def __repr__(self) -> str:
        """詳細表示"""
        return f"<Order {self.order_id} {self.contract} {self.side.value} {self.quantity}/{self.filled_quantity} {self.status.value}>"