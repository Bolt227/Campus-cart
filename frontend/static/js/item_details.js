const itemContainer = document.getElementById("itemContainer");
const itemId = window.location.pathname.split("/").pop();

async function loadItemDetails() {
  const response = await fetch(`/api/items/${itemId}`);

  if (!response.ok) {
    itemContainer.innerHTML =
      `<div class="empty-state"><span class="emoji">😕</span><h3>Item not found</h3><p>It may have been removed by the seller.</p><a class="btn btn-sm" href="/">Browse items</a></div>`;
    return;
  }

  const item = await response.json();
  document.title = `${item.title} - Campus Cart`;

  const image = item.image_path
    ? `<img class="item-image" src="${escapeHtml(item.image_path)}" alt="${escapeHtml(item.title)}">`
    : `<div class="no-image">No image available</div>`;

  const initial = escapeHtml((item.seller_name || "?").trim().charAt(0).toUpperCase());
  const sold = item.status === "sold";
  const mailSubject = encodeURIComponent(`Interested in: ${item.title}`);

  itemContainer.innerHTML = `
    <div class="detail">
      <div>${image}</div>

      <div class="detail-info">
        <div class="detail-tags">
          <span class="badge condition">${escapeHtml(item.item_condition)}</span>
          <span class="badge ${sold ? "sold" : "available"}">${sold ? "Sold" : "Available"}</span>
        </div>
        <p class="category">${escapeHtml(item.category)}</p>
        <h2>${escapeHtml(item.title)}</h2>
        <span class="price">₹${escapeHtml(item.price)}</span>
        <p class="desc">${escapeHtml(item.description)}</p>

        <div class="seller-card">
          <h3>Seller</h3>
          <div class="seller-row">
            <div class="avatar">${initial}</div>
            <div>
              <strong>${escapeHtml(item.seller_name)}</strong>
              <span>${escapeHtml(item.seller_email)}</span>
            </div>
          </div>
          <a class="btn btn-block" href="mailto:${escapeHtml(item.seller_email)}?subject=${mailSubject}">✉️ Contact seller</a>
        </div>
      </div>
    </div>
  `;
}

loadItemDetails();
