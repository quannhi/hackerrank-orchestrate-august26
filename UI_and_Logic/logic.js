const conversation = document.querySelector('.conversation'),
      input = document.querySelector('textarea'),
      top_bar_other = document.querySelector('.other'),
      messages = document.querySelector('.messages');

input.addEventListener('keydown', async (event) => {
    // Prevent default newline on Enter (allow Shift+Enter for newline)
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        
        const text = input.value.trim();
        if (!text) return;

        // Clear input field immediately
        input.value = '';

        // 1. Create and append the message DOM element instantly
        const messageEl = document.createElement('div');
        messageEl.classList.add('message', 'received');
        
        // Structure inner HTML to support a loading indicator + text + border
        messageEl.classList.add( 'status-loading')
        messageEl.innerHTML = `
            <div class="message-text">${escapeHtml(text)}</div>
        `;
        messages.appendChild(messageEl);
        messages.scrollTop = messages.scrollHeight; // Auto-scroll to bottom

        // 2. Fetch active sender ID from UI (e.g., from top_bar or dropdown)
        const selectedSenderId = top_bar_other.dataset.senderId || "SENDER_DEFAULT";

        try {
            // 3. Trigger API call to your Python backend
            const response = await fetch('http://localhost:8000/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    sender_id: selectedSenderId
                })
            });

            if (!response.ok) throw new Error('API server error');

            const result = await response.json();

            // 4. Update the DOM bubble with the agent's decision badge and details
            messageEl.classList.replace('status-loading', `status-${result.action.toLowerCase()}`)
            
            
            // Add hover/click tooltip showing grounded reason & evidence
            messageEl.title = `ACTION: ${result.action.toUpperCase()}\nReason: ${result.reason}\nEvidence: ${result.evidence_message_ids}`;

        } catch (error) {
            console.error("Routing request failed:", error);
            const statusEl = messageEl.querySelector('.message-status');
            statusEl.className = 'message-status status-error';
            statusEl.textContent = 'FAILED';
        }
    }
});

// Helper utility to sanitize html text nodes
function escapeHtml(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}