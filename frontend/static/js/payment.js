
const payButton = document.getElementById("pay-button");
const phoneInput = document.getElementById("customer-phone");
const message = document.getElementById("payment-message");

// Sandbox mode is only for testing.
const cashfree = Cashfree({
    mode: "sandbox"
});

payButton.addEventListener("click", async () => {
    const phone = phoneInput.value.trim();
    const productId = payButton.dataset.productId;

    if (!/^[6-9]\d{9}$/.test(phone)) {
        message.textContent = "Enter a valid 10-digit mobile number.";
        return;
    }

    payButton.disabled = true;
    message.textContent = "Creating your payment order...";

    try {
        const response = await fetch("/api/payments/create-order", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "same-origin",
            body: JSON.stringify({
                product_id: productId,
                customer_phone: phone
            })
        });

        const order = await response.json();

        if (!response.ok) {
            throw new Error(order.error || "Unable to create order");
        }

        message.textContent = "Opening Cashfree Checkout...";

        const result = await cashfree.checkout({
            paymentSessionId: order.payment_session_id,
            redirectTarget: "_self"
        });

        // Checkout errors are not proof of final payment status.
        if (result && result.error) {
            message.textContent =
                "Checkout encountered an issue. Check your order status.";
            payButton.disabled = false;
        }
    } catch (error) {
        message.textContent =
            error.message || "Could not start checkout.";
        payButton.disabled = false;
    }
});
