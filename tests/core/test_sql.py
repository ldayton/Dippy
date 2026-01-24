"""Comprehensive tests for SQL statement classification."""

from dippy.core.sql import is_readonly_sql


class TestBasicReadOnly:
    """Basic read-only statements."""

    def test_select(self):
        assert is_readonly_sql("SELECT * FROM users") is True

    def test_select_with_where(self):
        assert is_readonly_sql("SELECT id, name FROM users WHERE age > 30") is True

    def test_select_with_join(self):
        assert is_readonly_sql("SELECT * FROM a JOIN b ON a.id = b.a_id") is True

    def test_select_with_subquery(self):
        assert is_readonly_sql("SELECT * FROM (SELECT id FROM users) sub") is True

    def test_show(self):
        assert is_readonly_sql("SHOW TABLES") is True

    def test_show_columns(self):
        assert is_readonly_sql("SHOW COLUMNS FROM users") is True

    def test_describe(self):
        assert is_readonly_sql("DESCRIBE users") is True

    def test_explain(self):
        assert is_readonly_sql("EXPLAIN SELECT * FROM users") is True

    def test_explain_analyze_select(self):
        # EXPLAIN ANALYZE in some DBs executes, but we treat EXPLAIN as safe
        assert is_readonly_sql("EXPLAIN ANALYZE SELECT * FROM users") is True


class TestBasicWrite:
    """Basic write statements."""

    def test_insert(self):
        assert is_readonly_sql("INSERT INTO users (name) VALUES ('alice')") is False

    def test_insert_select(self):
        assert is_readonly_sql("INSERT INTO users SELECT * FROM other") is False

    def test_update(self):
        assert is_readonly_sql("UPDATE users SET name = 'bob' WHERE id = 1") is False

    def test_delete(self):
        assert is_readonly_sql("DELETE FROM users WHERE id = 1") is False

    def test_create_table(self):
        assert is_readonly_sql("CREATE TABLE users (id INT)") is False

    def test_create_index(self):
        assert is_readonly_sql("CREATE INDEX idx ON users(name)") is False

    def test_drop_table(self):
        assert is_readonly_sql("DROP TABLE users") is False

    def test_drop_index(self):
        assert is_readonly_sql("DROP INDEX idx") is False

    def test_alter_table(self):
        assert is_readonly_sql("ALTER TABLE users ADD COLUMN age INT") is False

    def test_truncate(self):
        assert is_readonly_sql("TRUNCATE TABLE users") is False

    def test_grant(self):
        assert is_readonly_sql("GRANT SELECT ON users TO alice") is False

    def test_revoke(self):
        assert is_readonly_sql("REVOKE SELECT ON users FROM alice") is False

    def test_merge(self):
        assert is_readonly_sql("MERGE INTO t USING s ON t.id = s.id") is False


class TestCTEs:
    """Common Table Expressions (WITH clauses)."""

    def test_cte_select(self):
        sql = "WITH cte AS (SELECT id FROM users) SELECT * FROM cte"
        assert is_readonly_sql(sql) is True

    def test_cte_insert(self):
        sql = "WITH cte AS (SELECT id FROM users) INSERT INTO other SELECT * FROM cte"
        assert is_readonly_sql(sql) is False

    def test_cte_delete(self):
        sql = "WITH cte AS (SELECT id FROM users) DELETE FROM users WHERE id IN (SELECT id FROM cte)"
        assert is_readonly_sql(sql) is False

    def test_multiple_ctes_select(self):
        sql = """
        WITH
            cte1 AS (SELECT id FROM users),
            cte2 AS (SELECT id FROM orders)
        SELECT * FROM cte1 JOIN cte2 ON cte1.id = cte2.id
        """
        assert is_readonly_sql(sql) is True

    def test_multiple_ctes_insert(self):
        sql = """
        WITH
            cte1 AS (SELECT id FROM users),
            cte2 AS (SELECT id FROM orders)
        INSERT INTO results SELECT * FROM cte1
        """
        assert is_readonly_sql(sql) is False

    def test_nested_cte_parens(self):
        sql = "WITH cte AS (SELECT (1 + 2) AS val) SELECT * FROM cte"
        assert is_readonly_sql(sql) is True

    def test_cte_with_recursive(self):
        sql = """
        WITH RECURSIVE cte AS (
            SELECT 1 AS n
            UNION ALL
            SELECT n + 1 FROM cte WHERE n < 10
        )
        SELECT * FROM cte
        """
        assert is_readonly_sql(sql) is True


class TestComments:
    """SQL comments handling."""

    def test_single_line_comment_before(self):
        sql = "-- this is a comment\nSELECT * FROM users"
        assert is_readonly_sql(sql) is True

    def test_single_line_comment_after(self):
        sql = "SELECT * FROM users -- get all users"
        assert is_readonly_sql(sql) is True

    def test_block_comment_before(self):
        sql = "/* comment */ SELECT * FROM users"
        assert is_readonly_sql(sql) is True

    def test_block_comment_inline(self):
        sql = "SELECT /* columns */ * FROM users"
        assert is_readonly_sql(sql) is True

    def test_block_comment_multiline(self):
        sql = """
        /*
         * Multi-line comment
         */
        SELECT * FROM users
        """
        assert is_readonly_sql(sql) is True

    def test_comment_containing_write_keyword(self):
        # DELETE in comment should be ignored
        sql = "-- DELETE everything\nSELECT * FROM users"
        assert is_readonly_sql(sql) is True

    def test_block_comment_containing_write_keyword(self):
        sql = "/* INSERT INTO users */ SELECT * FROM users"
        assert is_readonly_sql(sql) is True

    def test_multiple_comments(self):
        sql = "-- comment 1\n/* comment 2 */ SELECT * FROM users"
        assert is_readonly_sql(sql) is True


class TestWhitespace:
    """Whitespace handling."""

    def test_leading_whitespace(self):
        assert is_readonly_sql("   SELECT * FROM users") is True

    def test_leading_newlines(self):
        assert is_readonly_sql("\n\n\nSELECT * FROM users") is True

    def test_leading_tabs(self):
        assert is_readonly_sql("\t\tSELECT * FROM users") is True

    def test_mixed_whitespace(self):
        assert is_readonly_sql("  \n\t  SELECT * FROM users") is True

    def test_whitespace_and_comments(self):
        sql = "  \n-- comment\n  \nSELECT * FROM users"
        assert is_readonly_sql(sql) is True


class TestMultipleStatements:
    """Multiple statements (semicolon-separated)."""

    def test_two_selects(self):
        # Multiple statements should return None (unknown)
        sql = "SELECT 1; SELECT 2"
        assert is_readonly_sql(sql) is None

    def test_select_then_delete(self):
        sql = "SELECT * FROM users; DELETE FROM users"
        assert is_readonly_sql(sql) is None

    def test_trailing_semicolon_ok(self):
        # Single statement with trailing semicolon is fine
        sql = "SELECT * FROM users;"
        assert is_readonly_sql(sql) is True

    def test_trailing_semicolon_with_whitespace(self):
        sql = "SELECT * FROM users;  \n"
        assert is_readonly_sql(sql) is True

    def test_multiple_trailing_semicolons(self):
        # Multiple trailing semicolons - still single statement
        sql = "SELECT * FROM users;;;"
        assert is_readonly_sql(sql) is True

    def test_semicolon_in_middle(self):
        sql = "SELECT 1; "
        # Has content after semicolon (whitespace) - but trailing is OK
        assert is_readonly_sql(sql) is True

    def test_empty_statement_after_semicolon(self):
        sql = "SELECT 1;   ;  "
        # Multiple semicolons with whitespace between - ambiguous
        assert is_readonly_sql(sql) is None


class TestCaseInsensitivity:
    """Case insensitivity for keywords."""

    def test_lowercase_select(self):
        assert is_readonly_sql("select * from users") is True

    def test_uppercase_select(self):
        assert is_readonly_sql("SELECT * FROM USERS") is True

    def test_mixed_case_select(self):
        assert is_readonly_sql("SeLeCt * FrOm users") is True

    def test_lowercase_insert(self):
        assert is_readonly_sql("insert into users values (1)") is False

    def test_mixed_case_insert(self):
        assert is_readonly_sql("InSeRt INTO users VALUES (1)") is False


class TestExtraKeywords:
    """Dialect-specific extra keywords."""

    def test_extra_readonly_keyword(self):
        # Hypothetical dialect where FETCH is read-only
        sql = "FETCH NEXT FROM cursor"
        assert is_readonly_sql(sql) is None  # Unknown by default
        assert is_readonly_sql(sql, extra_readonly=frozenset({"FETCH"})) is True

    def test_extra_write_keyword_pragma(self):
        sql = "PRAGMA table_info(users)"
        assert is_readonly_sql(sql) is None  # Unknown by default
        assert is_readonly_sql(sql, extra_write=frozenset({"PRAGMA"})) is False

    def test_extra_write_keyword_vacuum(self):
        sql = "VACUUM"
        assert is_readonly_sql(sql) is None  # Unknown by default
        assert is_readonly_sql(sql, extra_write=frozenset({"VACUUM"})) is False

    def test_extra_write_keyword_attach(self):
        sql = "ATTACH DATABASE 'other.db' AS other"
        assert is_readonly_sql(sql) is None  # Unknown by default
        assert is_readonly_sql(sql, extra_write=frozenset({"ATTACH"})) is False

    def test_extra_write_keyword_detach(self):
        sql = "DETACH DATABASE other"
        assert is_readonly_sql(sql) is None  # Unknown by default
        assert is_readonly_sql(sql, extra_write=frozenset({"DETACH"})) is False

    def test_extra_write_msck(self):
        # Athena-specific
        sql = "MSCK REPAIR TABLE my_table"
        assert is_readonly_sql(sql) is None  # Unknown by default
        assert is_readonly_sql(sql, extra_write=frozenset({"MSCK"})) is False

    def test_extra_write_unload(self):
        # Athena-specific
        sql = "UNLOAD (SELECT * FROM t) TO 's3://bucket/'"
        assert is_readonly_sql(sql) is None  # Unknown by default
        assert is_readonly_sql(sql, extra_write=frozenset({"UNLOAD"})) is False

    def test_extra_keywords_combined(self):
        # Both extra_readonly and extra_write
        sql = "VACUUM"
        assert (
            is_readonly_sql(
                sql,
                extra_readonly=frozenset({"FETCH"}),
                extra_write=frozenset({"VACUUM"}),
            )
            is False
        )


class TestUnknownKeywords:
    """Unknown/unrecognized keywords."""

    def test_unknown_keyword(self):
        sql = "FOOBAR something"
        assert is_readonly_sql(sql) is None

    def test_unknown_dialect_specific(self):
        sql = "CALL stored_procedure()"
        assert is_readonly_sql(sql) is None

    def test_set_statement(self):
        # SET could be read or write depending on dialect
        sql = "SET search_path TO myschema"
        assert is_readonly_sql(sql) is None


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_string(self):
        assert is_readonly_sql("") is None

    def test_only_whitespace(self):
        assert is_readonly_sql("   \n\t  ") is None

    def test_only_comment(self):
        assert is_readonly_sql("-- just a comment") is None

    def test_only_block_comment(self):
        assert is_readonly_sql("/* just a comment */") is None

    def test_incomplete_statement(self):
        # No actual statement, just keyword
        assert is_readonly_sql("SELECT") is True  # Still identified as SELECT

    def test_select_no_from(self):
        assert is_readonly_sql("SELECT 1") is True

    def test_select_expression(self):
        assert is_readonly_sql("SELECT 1 + 2 * 3") is True

    def test_very_long_sql(self):
        # Ensure no performance issues with long SQL
        sql = "SELECT " + ", ".join([f"col{i}" for i in range(1000)]) + " FROM t"
        assert is_readonly_sql(sql) is True


class TestExplainVariants:
    """EXPLAIN with various statements."""

    def test_explain_select(self):
        assert is_readonly_sql("EXPLAIN SELECT * FROM users") is True

    def test_explain_insert(self):
        # EXPLAIN doesn't execute, so this is still safe
        assert is_readonly_sql("EXPLAIN INSERT INTO t VALUES (1)") is True

    def test_explain_delete(self):
        assert is_readonly_sql("EXPLAIN DELETE FROM users") is True

    def test_explain_update(self):
        assert is_readonly_sql("EXPLAIN UPDATE users SET x = 1") is True

    def test_explain_plan(self):
        assert is_readonly_sql("EXPLAIN PLAN FOR SELECT * FROM users") is True


class TestAthenaDialect:
    """Athena-specific SQL patterns."""

    ATHENA_WRITE = frozenset({"MSCK", "UNLOAD", "VACUUM"})

    def test_athena_msck_repair(self):
        sql = "MSCK REPAIR TABLE my_table"
        assert is_readonly_sql(sql, extra_write=self.ATHENA_WRITE) is False

    def test_athena_unload(self):
        sql = "UNLOAD (SELECT * FROM t) TO 's3://bucket/path'"
        assert is_readonly_sql(sql, extra_write=self.ATHENA_WRITE) is False

    def test_athena_vacuum(self):
        sql = "VACUUM my_iceberg_table"
        assert is_readonly_sql(sql, extra_write=self.ATHENA_WRITE) is False

    def test_athena_select(self):
        sql = "SELECT * FROM my_table"
        assert is_readonly_sql(sql, extra_write=self.ATHENA_WRITE) is True

    def test_athena_show_tables(self):
        sql = "SHOW TABLES IN my_database"
        assert is_readonly_sql(sql, extra_write=self.ATHENA_WRITE) is True

    def test_athena_describe(self):
        sql = "DESCRIBE my_table"
        assert is_readonly_sql(sql, extra_write=self.ATHENA_WRITE) is True


class TestSQLiteDialect:
    """SQLite-specific SQL patterns."""

    SQLITE_WRITE = frozenset(
        {"PRAGMA", "ATTACH", "DETACH", "VACUUM", "REINDEX", "ANALYZE"}
    )

    def test_sqlite_pragma(self):
        sql = "PRAGMA table_info(users)"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_pragma_set(self):
        sql = "PRAGMA foreign_keys = ON"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_attach(self):
        sql = "ATTACH DATABASE 'other.db' AS other"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_detach(self):
        sql = "DETACH DATABASE other"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_vacuum(self):
        sql = "VACUUM"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_vacuum_into(self):
        sql = "VACUUM INTO 'backup.db'"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_reindex(self):
        sql = "REINDEX"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_analyze(self):
        sql = "ANALYZE"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is False

    def test_sqlite_select(self):
        sql = "SELECT * FROM users"
        assert is_readonly_sql(sql, extra_write=self.SQLITE_WRITE) is True


class TestSelectInto:
    """SELECT INTO creates a new table - this is a write operation."""

    def test_select_into_basic(self):
        # SELECT INTO creates a new table (SQL Server, PostgreSQL)
        sql = "SELECT * INTO new_table FROM users"
        assert is_readonly_sql(sql) is False

    def test_select_into_with_where(self):
        sql = "SELECT id, name INTO backup_users FROM users WHERE active = 1"
        assert is_readonly_sql(sql) is False

    def test_select_into_temp(self):
        sql = "SELECT * INTO #temp_table FROM users"
        assert is_readonly_sql(sql) is False

    def test_select_into_with_join(self):
        sql = "SELECT a.*, b.name INTO results FROM a JOIN b ON a.id = b.a_id"
        assert is_readonly_sql(sql) is False


class TestUpsertVariants:
    """UPSERT/REPLACE operations across different database dialects."""

    def test_insert_or_replace(self):
        # SQLite syntax
        sql = "INSERT OR REPLACE INTO users (id, name) VALUES (1, 'alice')"
        assert is_readonly_sql(sql) is False

    def test_insert_or_ignore(self):
        sql = "INSERT OR IGNORE INTO users (id, name) VALUES (1, 'alice')"
        assert is_readonly_sql(sql) is False

    def test_replace_into(self):
        # MySQL/SQLite syntax
        sql = "REPLACE INTO users (id, name) VALUES (1, 'alice')"
        assert is_readonly_sql(sql) is False

    def test_insert_on_conflict_do_nothing(self):
        # PostgreSQL/SQLite syntax
        sql = "INSERT INTO users (id) VALUES (1) ON CONFLICT DO NOTHING"
        assert is_readonly_sql(sql) is False

    def test_insert_on_conflict_do_update(self):
        sql = "INSERT INTO users (id, name) VALUES (1, 'a') ON CONFLICT (id) DO UPDATE SET name = 'b'"
        assert is_readonly_sql(sql) is False

    def test_insert_on_duplicate_key(self):
        # MySQL syntax
        sql = "INSERT INTO users (id, name) VALUES (1, 'a') ON DUPLICATE KEY UPDATE name = 'b'"
        assert is_readonly_sql(sql) is False


class TestStringLiterals:
    """Keywords and special characters inside string literals."""

    def test_keyword_in_single_quoted_string(self):
        sql = "SELECT * FROM logs WHERE action = 'DELETE'"
        assert is_readonly_sql(sql) is True

    def test_keyword_in_double_quoted_string(self):
        sql = 'SELECT * FROM logs WHERE action = "DELETE"'
        assert is_readonly_sql(sql) is True

    def test_semicolon_in_string(self):
        sql = "SELECT 'foo;bar' AS val"
        assert is_readonly_sql(sql) is True

    def test_escaped_quote_in_string(self):
        sql = "SELECT 'it''s a test' AS val"
        assert is_readonly_sql(sql) is True

    def test_multiple_strings_with_keywords(self):
        sql = "SELECT 'INSERT', 'UPDATE', 'DELETE' AS keywords"
        assert is_readonly_sql(sql) is True


class TestIdentifierQuoting:
    """Quoted identifiers containing keywords."""

    def test_backtick_identifier_with_keyword(self):
        # MySQL style
        sql = "SELECT `DELETE` FROM users"
        assert is_readonly_sql(sql) is True

    def test_bracket_identifier_with_keyword(self):
        # SQL Server style
        sql = "SELECT [DELETE] FROM users"
        assert is_readonly_sql(sql) is True

    def test_double_quote_identifier_with_keyword(self):
        # PostgreSQL/standard style
        sql = 'SELECT "DELETE" FROM users'
        assert is_readonly_sql(sql) is True

    def test_backtick_table_name(self):
        sql = "SELECT * FROM `DROP`"
        assert is_readonly_sql(sql) is True

    def test_bracket_table_name(self):
        sql = "SELECT * FROM [INSERT]"
        assert is_readonly_sql(sql) is True
