def build_subscription_event(
    *,
    status,
    customer_id="cus_test",
    subscription_id="sub_test",
    metadata=None,
    cancel_at_period_end=False,
    **overrides,
):
    data = {
        "id": subscription_id,
        "customer": customer_id,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "metadata": metadata or {},
    }
    data.update(overrides)
    return {
        "id": "evt_test",
        "data": {"object": data},
    }


def build_checkout_completed_event(
    *,
    customer_id="cus_test",
    checkout_id="cs_test",
    payment_status="paid",
    mode="payment",
    metadata=None,
    **overrides,
):
    data = {
        "id": checkout_id,
        "customer": customer_id,
        "payment_status": payment_status,
        "mode": mode,
        "metadata": metadata or {},
    }
    data.update(overrides)
    return {
        "id": "evt_checkout",
        "data": {"object": data},
    }
