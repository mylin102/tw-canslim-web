from importlib import import_module

import pandas as pd

from excel_processor import ExcelDataProcessor


def test_health_check_loader_merges_summary_and_rating_sheets(tmp_path):
    workbook = tmp_path / "股票健診60417.xlsx"

    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                [3167, "大量"],
            ]
        ).to_excel(writer, sheet_name="Sheet1", header=False, index=False)

        pd.DataFrame(
            [
                {
                    "股票代號": 1101,
                    "股票名稱": "台泥",
                    "近一季EPS成長率(%)": 38.2,
                    "三季平均EPS成長率(%)": 28.5,
                    "去年EPS成長率(%)": 31.0,
                    "三年EPS成長率(%)": 26.0,
                    "EPS連續成長年數": 2,
                    "近一季營收成長率": 18.0,
                    "三季平均營收成長率": 17.0,
                    "基金持有家數Q-0": 8,
                    "基金持有家數Q-1": 7,
                    "基金家數增加季數": 1,
                    "三大法人持股比例(%D)": 20.09,
                    "三大法人持股變化率(%D)": 0.8,
                }
            ]
        ).to_excel(writer, sheet_name="綜合資料", index=False)

        pd.DataFrame(
            [
                {"代號": 2454, "名稱": "聯發科", "Composite Rating": 97},
            ]
        ).to_excel(writer, sheet_name="Composite Rating", index=False)

        pd.DataFrame([[2454, 86]]).to_excel(writer, sheet_name="EPS Rating", header=False, index=False)
        pd.DataFrame([[2454, 99]]).to_excel(writer, sheet_name="RS Rating", header=False, index=False)
        pd.DataFrame(
            [
                {"代碼": 2454, "商品": "聯發科", "SMR Rating": "A"},
            ]
        ).to_excel(writer, sheet_name="SMR Rating", index=False)
        pd.DataFrame(
            [
                [1101, 20.09, 408, 73.5, 73, 74, 147, 74.7, 74, "B+"],
                [2454, 33.6, 267, 85.5, 85, 80, 165, 83.6, 83, "A-"],
            ]
        ).to_excel(writer, sheet_name="Sponsorship Rating", header=False, index=False)
        pd.DataFrame(
            [
                {
                    "股票名稱": 2454,
                    "股票名稱.1": "2454聯發科",
                    "漲跌": 30,
                    "漲跌幅": 0.0158,
                    "本月投信基金持股檔數": 267,
                    "上月投信基金持股檔數": 167,
                }
            ]
        ).to_excel(writer, sheet_name="基金持有檔數", index=False)

    processor = ExcelDataProcessor(str(tmp_path))
    health = processor.load_health_check_data()
    funds = processor.load_fund_holdings_data()

    assert health["1101"]["quarterly_eps_growth_pct"] == 38.2
    assert health["1101"]["annual_eps_growth_pct"] == 31.0
    assert health["1101"]["sponsorship_score"] == 74.7
    assert health["1101"]["sponsorship_rating"] == "B+"

    assert health["2454"]["composite_rating"] == 97.0
    assert health["2454"]["eps_rating"] == 86.0
    assert health["2454"]["rs_rating"] == 99.0
    assert health["2454"]["smr_rating"] == "A"
    assert health["2454"]["sponsorship_rating"] == "A-"

    assert funds["2454"]["current_month"] == 267
    assert funds["2454"]["previous_month"] == 167
    assert funds["2454"]["change"] == 100


def test_canslim_engine_excel_fallbacks_cover_c_a_and_i():
    module = import_module("export_canslim")
    engine = object.__new__(module.CanslimEngine)
    engine.excel_ratings = {
        "2330": {
            "quarterly_eps_growth_pct": 35.0,
            "annual_eps_growth_pct": 42.0,
            "eps_rating": 85.0,
            "institutional_holding_pct": 22.5,
            "sponsorship_score": 72.0,
        }
    }
    engine.fund_holdings = {
        "2330": {
            "current_month": 120,
            "change": 10,
            "change_pct": 9.1,
        }
    }

    assert engine._excel_c_fallback("2330") is True
    assert engine._excel_a_fallback("2330") is True

    score, details = engine._excel_i_fallback("2330", 0.0)
    assert score >= 72.0
    assert details["source"] == "excel_fallback"
    assert details["institutional_holding_pct"] == 22.5
