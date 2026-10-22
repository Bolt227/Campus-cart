"use strict";

// Get the item container and item ID from the URL.
const itemContainer = document.getElementById("itemContainer");
const itemId = window.location.pathname.split("/").filter(Boolean).pop();

// Load item details when the page opens.
async function loadItemDetails() {
  if (!itemContainer) {
    console.error("Item container not found.");
    return;
  }

  if (!itemId || !/^\d+$/.test(itemId)) {
    showItemError();
    return;
  }

  try {
    const response = await fetch(`/api/items/${encodeURIComponent(itemId)}`, {
      credentials: "same-origin"
    });

    if (response.status === 404) {
      showItemError();
      return;
    }

    if (!response.ok) {
      showItemError(
        "Something went wrong on our side. Please try again later.",
        "Could not load item"
      );
      return;
    }

    const item = await response.json();

    document.title = `${item.title || "Item"} - Campus Cart`;

    // Display the item image only if it is a safe, local or https URL.
    const imageSrc = safeImageSrc(item.image_path);
    const image = imageSrc
      ? `<img class="item-image"
              src="${escapeHtml(imageSrc)}"
              alt="${escapeHtml(item.title || "Item")}">`
      : `<div class="no-image">No image available</div>`;

    // First letter of the seller's name for the avatar.
    const initial = escapeHtml(
      (item.seller_name || "?").trim().charAt(0).toUpperCase()
    );

    // Check whether the item is unavailable for purchase.
    const status = String(item.status || "available").toLowerCase();
    const sold = status === "sold";
    const pending = status === "pending";

    // Price: build the whole string so the ₹ sign is not shown without a number.
    const hasPrice =
      item.price !== null && item.price !== undefined && item.price !== "";
    const priceText = hasPrice
      ? `₹${escapeHtml(item.price)}`
      : "Price unavailable";

    const sellerEmail = String(item.seller_email || "");
    const mailSubject = encodeURIComponent(
      `Interested in: ${item.title || "this item"}`
    );

    // Purchase section depends on the item status.
    let purchaseSection;
    if (sold) {
      purchaseSection = `<p>This item has already been sold.</p>`;
    } else if (pending) {
      purchaseSection = `<p>A payment for this item is in progress. Please check back shortly.</p>`;
    } else {
      purchaseSection = `
        <div class="checkout-section">
          <h3>Buy this item</h3>

          <label for="customer-phone">Mobile number</label>
          <input
            type="tel"
            id="customer-phone"
            placeholder="10-digit Indian mobile number"
            maxlength="14"
            inputmode="numeric"
            autocomplete="tel"
          >

          <button class="btn btn-block" id="checkout-btn" type="button">
            Buy Now
          </button>

          <p id="payment-message" role="status"></p>
        </div>
      `;
    }

    // Render the complete item details page.
    itemContainer.innerHTML = `
      <div class="detail">
        <div>
          ${image}
        </div>

        <div class="detail-info">
          <div class="detail-tags">
            <span class="badge condition">
              ${escapeHtml(item.item_condition || "Not specified")}
            </span>
            <span class="badge ${sold ? "sold" : "available"}">
              ${sold ? "Sold" : pending ? "Pending" : "Available"}
            </span>
          </div>

          <p class="category">${escapeHtml(item.category || "Other")}</p>
          <h2>${escapeHtml(item.title || "Untitled item")}</h2>
          <span class="price">${priceText}</span>
          <p class="desc">${escapeHtml(item.description || "")}</p>

          ${purchaseSection}

          <div class="seller-card">
            <h3>Seller</h3>

            <div class="seller-row">
              <div class="avatar">${initial}</div>
              <div>
                <strong>
                  ${escapeHtml(item.seller_name || "Campus Cart seller")}
                </strong>
              </div>
            </div>

            ${
              sellerEmail
                ? `<a
                    class="btn btn-block"
                    href="mailto:${escapeHtml(sellerEmail)}?subject=${mailSubject}"
                  >
                    ✉️ Contact seller
                  </a>`
                : ""
            }
          </div>
        </div>
      </div>
    `;

    // Connect the Buy Now button to the checkout function.
    const checkoutButton = document.getElementById("checkout-btn");

    if (checkoutButton) {
      checkoutButton.addEventListener("click", function () {
        startCheckout(item);
      });
    }
  } catch (error) {
    console.error("Error loading item details:", error);
    showItemError(
      "Unable to load item details. Please check your connection and try again.",
      "Could not load item"
    );
  }
}

// Display an error when an item cannot be loaded.
function showItemError(
  message = "It may have been removed by the seller.",
  title = "Item not found"
) {
  if (!itemContainer) {
    return;
  }

  itemContainer.innerHTML = `
    <div class="empty-state">
      <span class="emoji">😕</span>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(message)}</p>
      <a class="btn btn-sm" href="/">Browse items</a>
    </div>
  `;
}

// Normalise an Indian mobile number to 10 digits (handles +91, 91, 0 prefixes).
function normalizePhone(raw) {
  let digits = String(raw || "").replace(/\D/g, "");

  if (digits.length === 12 && digits.startsWith("91")) {
    digits = digits.slice(2);
  } else if (digits.length === 11 && digits.startsWith("0")) {
    digits = digits.slice(1);
  }

  return digits;
}

// Start the Cashfree payment process.
async function startCheckout(item) {
  const button = document.getElementById("checkout-btn");
  const phoneInput = document.getElementById("customer-phone");
  const message = document.getElementById("payment-message");

  if (!button || !phoneInput || !message) {
    return;
  }

  // Ignore repeated clicks while a request is already running.
  if (button.disabled) {
    return;
  }

  const phone = normalizePhone(phoneInput.value);

  // Validate the mobile number.
  if (!/^[6-9]\d{9}$/.test(phone)) {
    message.textContent = "Enter a valid 10-digit Indian mobile number.";
    return;
  }

  // Do not allow payment for an item that is not available.
  if (String(item.status || "available").toLowerCase() !== "available") {
    message.textContent = "This item is no longer available.";
    return;
  }

  // Check that the Cashfree SDK has loaded.
  if (typeof window.Cashfree !== "function") {
    message.textContent =
      "Cashfree could not load. Check your internet connection and refresh.";
    return;
  }

  button.disabled = true;
  message.textContent = "Creating payment order...";

  try {
    // Ask Flask to create the payment order. The server must look up the
    // price itself and must never trust a price sent from the browser.
    const response = await fetch("/api/payments/create-order", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({
        item_id: item.id ?? itemId,
        customer_phone: phone
      })
    });

    let data = {};
    try {
      data = await response.json();
    } catch (parseError) {
      // Non-JSON response; fall through to the generic error below.
    }

    if (!response.ok) {
      throw new Error(
        data.error || data.message || "Could not create payment order."
      );
    }

    if (!data.payment_session_id) {
      throw new Error("The server did not return a payment session.");
    }

    // The backend decides the mode ("sandbox" or "production").
    const cashfree = window.Cashfree({
      mode: data.mode === "production" ? "production" : "sandbox"
    });

    message.textContent = "Opening Cashfree checkout...";

    // Open the secure Cashfree checkout page.
    const result = await cashfree.checkout({
      paymentSessionId: data.payment_session_id,
      redirectTarget: "_self"
    });

    // If checkout returns an error, the page did not redirect.
    if (result && result.error) {
      throw new Error(result.error.message || "Payment could not be completed.");
    }

    // On success the browser redirects, so the button stays disabled
    // to prevent a second order from being created.
  } catch (error) {
    console.error("Payment error:", error);

    message.textContent =
      error.message || "Payment could not be started. Please try again.";

    // Re-enable only when something went wrong.
    button.disabled = false;
  }
}

// Allow only local upload paths or https image URLs.
function safeImageSrc(path) {
  const value = String(path || "").trim();

  if (!value) {
    return "";
  }

  if (value.startsWith("/") && !value.startsWith("//")) {
    return value;
  }

  if (/^https:\/\//i.test(value)) {
    return value;
  }

  return "";
}

// Escape HTML characters before displaying API data.
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, function (character) {
    const replacements = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    };

    return replacements[character];
  });
}

// Load the page.
loadItemDetails();