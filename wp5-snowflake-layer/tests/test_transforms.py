from __future__ import annotations

from unittest.mock import call, patch

import pytest


class TestSilverTransforms:
    def test_run_silver_executes_statements(self, mock_sf, tmp_path):
        sql = "MERGE INTO silver_sensor_readings USING (...) ON (...) WHEN NOT MATCHED THEN INSERT (...)"
        sql_file = tmp_path / "silver_transforms.sql"
        sql_file.write_text(sql)

        from src.transforms.silver import run_silver

        run_silver(str(tmp_path))

        mock_sf.execute.assert_called_once_with(sql.strip())

    def test_run_silver_skips_empty_statements(self, mock_sf, tmp_path):
        sql = "STMT_ONE; ; STMT_TWO"
        sql_file = tmp_path / "silver_transforms.sql"
        sql_file.write_text(sql)

        from src.transforms.silver import run_silver

        run_silver(str(tmp_path))

        assert mock_sf.execute.call_count == 2
        calls = [c[0][0] for c in mock_sf.execute.call_args_list]
        assert "STMT_ONE" in calls
        assert "STMT_TWO" in calls

    def test_run_silver_raises_on_query_error(self, mock_sf, tmp_path):
        from src.exceptions import SnowflakeQueryError

        mock_sf.execute.side_effect = SnowflakeQueryError("MERGE failed")
        sql_file = tmp_path / "silver_transforms.sql"
        sql_file.write_text("SOME SQL")

        from src.transforms.silver import run_silver

        with pytest.raises(SnowflakeQueryError):
            run_silver(str(tmp_path))


class TestGoldTransforms:
    def test_run_gold_executes_statements(self, mock_sf, tmp_path):
        sql = "MERGE INTO gold_cycle_summary USING (...) ON (...) WHEN NOT MATCHED THEN INSERT (...)"
        sql_file = tmp_path / "gold_transforms.sql"
        sql_file.write_text(sql)

        from src.transforms.gold import run_gold

        run_gold(str(tmp_path))

        mock_sf.execute.assert_called_once_with(sql.strip())

    def test_run_gold_skips_empty_statements(self, mock_sf, tmp_path):
        sql = "GOLD_STMT_ONE; ; GOLD_STMT_TWO"
        sql_file = tmp_path / "gold_transforms.sql"
        sql_file.write_text(sql)

        from src.transforms.gold import run_gold

        run_gold(str(tmp_path))

        assert mock_sf.execute.call_count == 2

    def test_run_gold_raises_on_query_error(self, mock_sf, tmp_path):
        from src.exceptions import SnowflakeQueryError

        mock_sf.execute.side_effect = SnowflakeQueryError("MERGE failed")
        sql_file = tmp_path / "gold_transforms.sql"
        sql_file.write_text("GOLD SQL")

        from src.transforms.gold import run_gold

        with pytest.raises(SnowflakeQueryError):
            run_gold(str(tmp_path))
