DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lector_cloudvault') THEN
        CREATE ROLE lector_cloudvault WITH LOGIN PASSWORD 'CloudVault_ReadOnly_2026!';
    END IF;

    GRANT CONNECT ON DATABASE railway TO lector_cloudvault;
    GRANT USAGE ON SCHEMA public TO lector_cloudvault;

    GRANT SELECT ON ALL TABLES IN SCHEMA public TO lector_cloudvault;
    GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO lector_cloudvault;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO lector_cloudvault;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO lector_cloudvault;
END
$$; --