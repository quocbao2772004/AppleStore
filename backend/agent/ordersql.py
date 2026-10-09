"""Atomic order write. Ranking stays in Python; only this write lives in PostgreSQL.

place_shop_order is a function, not a procedure, so one SELECT is one transaction
under autocommit and a test transaction can roll it back. A BEFORE UPDATE trigger
rejects stock below zero. The function catches that rejection and returns ok=false
without inserting an order.
"""

_REJECT_STOCK = """
CREATE OR REPLACE FUNCTION reject_negative_stock()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.stock < 0 THEN
        RAISE EXCEPTION 'stock_below_zero';
    END IF;
    RETURN NEW;
END;
$$;
"""

_DROP_TRIGGER = "DROP TRIGGER IF EXISTS products_stock_nonnegative ON products"

_CREATE_TRIGGER = """
CREATE TRIGGER products_stock_nonnegative
BEFORE UPDATE OF stock ON products
FOR EACH ROW
EXECUTE FUNCTION reject_negative_stock()
"""

_PLACE_ORDER = """
CREATE OR REPLACE FUNCTION place_shop_order(
    p_user_id bigint,
    p_product_id bigint,
    p_qty integer,
    p_color text,
    p_ship_name text,
    p_ship_email text,
    p_ship_phone text,
    p_ship_address text,
    p_deliver_on date,
    p_deliver_slot text,
    p_pay_method text
) RETURNS TABLE (
    ok boolean,
    order_id bigint,
    stock_left integer,
    unit_price bigint,
    product_name text,
    note text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_name text;
    v_price bigint;
    v_stock integer;
    v_left integer;
    v_order bigint;
    v_label text;
BEGIN
    IF p_qty IS NULL OR p_qty < 1 OR p_qty > 5 THEN
        ok := false;
        note := 'Số lượng từ 1 đến 5.';
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT name, price_vnd, stock
      INTO v_name, v_price, v_stock
      FROM products
     WHERE source_product_id = p_product_id
       AND is_live_catalog
     FOR UPDATE;

    IF NOT FOUND THEN
        ok := false;
        note := 'Không thấy sản phẩm.';
        RETURN NEXT;
        RETURN;
    END IF;

    product_name := v_name;
    unit_price := v_price;
    stock_left := v_stock;

    IF v_stock IS NULL OR v_stock <= 0 THEN
        ok := false;
        note := 'Sản phẩm đã hết hàng.';
        RETURN NEXT;
        RETURN;
    END IF;

    v_label := v_name;
    IF coalesce(btrim(p_color), '') <> '' THEN
        v_label := v_name || ' (' || btrim(p_color) || ')';
    END IF;

    BEGIN
        UPDATE products
           SET stock = stock - p_qty
         WHERE source_product_id = p_product_id
        RETURNING stock INTO v_left;

        INSERT INTO orders (
            user_id, total_vnd, ship_name, ship_email, ship_phone, ship_address,
            deliver_on, deliver_slot, pay_method
        ) VALUES (
            p_user_id, v_price * p_qty, p_ship_name, p_ship_email, p_ship_phone, p_ship_address,
            p_deliver_on, p_deliver_slot, coalesce(nullif(btrim(p_pay_method), ''), 'cod')
        ) RETURNING id INTO v_order;

        INSERT INTO order_items (order_id, product_id, name, unit_price, qty)
        VALUES (v_order, p_product_id, v_label, v_price, p_qty);

        ok := true;
        order_id := v_order;
        stock_left := v_left;
        unit_price := v_price;
        product_name := v_name;
        note := '';
        RETURN NEXT;
    EXCEPTION
        WHEN raise_exception THEN
            ok := false;
            order_id := NULL;
            stock_left := v_stock;
            unit_price := v_price;
            product_name := v_name;
            note := 'Chỉ còn ' || v_stock || ' máy.';
            RETURN NEXT;
    END;
END;
$$;
"""


_READY = False


def ensure_order_sql(conn):
    """Create the stock guard and the order function. Safe to run more than once.

    A committed connection can skip later calls. A transaction always re-applies
    the statements, so a rollback cannot leave this process believing the
    function exists when that transaction was the only place it was created.
    """
    global _READY
    if _READY and conn.autocommit:
        return
    conn.execute(_REJECT_STOCK)
    conn.execute(_DROP_TRIGGER)
    conn.execute(_CREATE_TRIGGER)
    conn.execute(_PLACE_ORDER)
    if conn.autocommit:
        _READY = True
