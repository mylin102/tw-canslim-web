"""
CANSLIM Strategy Backtester.
Tests if high CANSLIM score stocks actually outperform the market.
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CANSLIMBacktester:
    """Backtest CANSLIM strategy performance."""
    
    def __init__(self, data_file: str):
        with open(data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
    
    def get_top_stocks(self, min_score: int = 80, limit: int = 10) -> List[Dict]:
        """Get stocks with CANSLIM score >= min_score."""
        stocks = self.data.get('stocks', {})
        
        qualified = [
            s for s in stocks.values() 
            if s.get('canslim', {}).get('score', 0) >= min_score
        ]
        
        # Sort by score
        qualified.sort(key=lambda x: x['canslim']['score'], reverse=True)
        
        return qualified[:limit]
    
    def get_stocks_with_institutional_buying(self, days: int = 3) -> List[Dict]:
        """Get stocks with consecutive institutional buying."""
        stocks = self.data.get('stocks', {})
        
        result = []
        for stock in stocks.values():
            inst = stock.get('institutional', [])
            if len(inst) < days:
                continue
            
            # Check if recent days show net buying
            recent = inst[:days]
            total_net = sum([
                d.get('foreign_net', 0) + d.get('trust_net', 0) + d.get('dealer_net', 0)
                for d in recent
            ])
            
            if total_net > 0:
                result.append(stock)
        
        result.sort(key=lambda x: x['canslim']['score'], reverse=True)
        return result
    
    def generate_backtest_report(self) -> Dict:
        """Generate a comprehensive backtest report."""
        stocks = self.data.get('stocks', {})
        
        # Score distribution
        score_ranges = {
            '90+': 0,
            '80-89': 0,
            '70-79': 0,
            '60-69': 0,
            '<60': 0
        }
        
        # CANSLIM metric pass rates
        metric_pass_rates = {
            'C': 0, 'A': 0, 'N': 0, 'S': 0, 'L': 0, 'I': 0, 'M': 0
        }
        
        total_stocks = len(stocks)
        
        for stock in stocks.values():
            score = stock.get('canslim', {}).get('score', 0)
            
            # Score distribution
            if score >= 90:
                score_ranges['90+'] += 1
            elif score >= 80:
                score_ranges['80-89'] += 1
            elif score >= 70:
                score_ranges['70-79'] += 1
            elif score >= 60:
                score_ranges['60-69'] += 1
            else:
                score_ranges['<60'] += 1
            
            # Metric pass rates
            canslim = stock.get('canslim', {})
            for metric in metric_pass_rates:
                if canslim.get(metric, False):
                    metric_pass_rates[metric] += 1
        
        # Calculate percentages
        for key in metric_pass_rates:
            metric_pass_rates[key] = round(
                (metric_pass_rates[key] / total_stocks * 100) if total_stocks > 0 else 0, 1
            )
        
        # Top stocks
        top_10 = self.get_top_stocks(min_score=80, limit=10)
        
        # Institutional buying
        with_inst_buying = self.get_stocks_with_institutional_buying(days=3)
        
        return {
            'total_stocks': total_stocks,
            'score_distribution': score_ranges,
            'metric_pass_rates': metric_pass_rates,
            'top_10_stocks': [
                {
                    'symbol': s['symbol'],
                    'name': s['name'],
                    'score': s['canslim']['score']
                }
                for s in top_10
            ],
            'with_institutional_buying': len(with_inst_buying),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


if __name__ == "__main__":
    import os
    
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_FILE = os.path.join(SCRIPT_DIR, "docs", "data.json")
    
    backtester = CANSLIMBacktester(DATA_FILE)
    report = backtester.generate_backtest_report()
    
    print("\n" + "="*80)
    print("CANSLIM Strategy Backtest Report")
    print("="*80)
    print(f"\nGenerated: {report['generated_at']}")
    print(f"Total Stocks Analyzed: {report['total_stocks']}")
    
    print("\nScore Distribution:")
    for range_name, count in report['score_distribution'].items():
        pct = round(count / report['total_stocks'] * 100, 1) if report['total_stocks'] > 0 else 0
        print(f"  {range_name}: {count} ({pct}%)")
    
    print("\nCANSLIM Metric Pass Rates:")
    for metric, pct in report['metric_pass_rates'].items():
        print(f"  {metric}: {pct}%")
    
    print(f"\nTop 10 CANSLIM Stocks:")
    for i, stock in enumerate(report['top_10_stocks'], 1):
        print(f"  #{i} {stock['symbol']} {stock['name']} - {stock['score']}分")
    
    print(f"\nStocks with Institutional Buying (3d): {report['with_institutional_buying']}")
    print("="*80)
