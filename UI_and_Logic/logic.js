import Papa from 'papaparse'
function parseCSV(url) {
  return new Promise((resolve, reject) => {
    Papa.parse(url, {
      header: true,
      download: true,
      complete: function(results) {
        resolve(results.data); // Resolves the promise with the iterable array
      },
      error: function(error) {
        reject(error);
      }
    });
  });
}
const conversation = document.querySelector('.conversation'),
      input = document.querySelector('textarea'),
      top_bar_other = document.querySelector('.other'),
      top_bar_owner = document.querySelector('.owner'),
      messages = document.querySelector('.messages'),
      users = document.querySelector('.users'),
      user = document.querySelector('.user')

function resetUsers(){
    users.innerHTML = ''
}

async function loadAndParseJSON() {
    try {
        const response = await fetch('./information.json');
        const data = await response.json(); 
        
        return data
    } catch (error) {
        console.error("Failed to parse JSON:", error);
    }
}
async function createLists(){
    const information_users = await loadAndParseJSON(),
          information_history = await parseCSV('../dataset/message_history.csv')
    console.log(information_users)
    console.log(information_history)
    // create users list to choose
    let width_owner = top_bar_owner.offsetWidth,
        is_open = false
    
    const user_choice = document.createElement('select'),
          img = document.createElement('img'),
          top_text = top_bar_owner.querySelector('.top.owner'),
          bottom_text = top_bar_owner.querySelector('.bottom.owner')
    
    img.src='icons/placeholder_icon.png'
    img.style.height = '75px'

    user_choice.name = 'user'
    user_choice.style.width= (width_owner - 1) + 'px'
    user_choice.classList.add('user_choice')

    const option = document.createElement('option')
    option.style.minHeight= user.offsetHeight + 'px'

    for (let user_info of Object.values(information_users)){
        // creating the user options
        const clone = option.cloneNode(true),
              clone_user = user.cloneNode(true),
              top_text_clone = clone_user.querySelector('.top'),
              bottom_text_clone = clone_user.querySelector('.bottom')

        clone.value = user_info.user_id
        top_text_clone.textContent = user_info.archetype
        bottom_text_clone.textContent = user_info.description
        clone.appendChild(clone_user)
        user_choice.appendChild(clone)

        clone.addEventListener('click', (event)=>{
            resetUsers()
            messages.innerHTML=''
            let history = {}
            clone.selected = true
            top_text.textContent = top_text_clone.textContent
            bottom_text.textContent = bottom_text_clone.textContent
            // creating the list of senders
            const interacted = user_info.interacted_users
            for (let sender of interacted){
                for (let message of information_history){
                    let senderId = message.sender_user_id
                    if (senderId === sender) {
                        console.log(message.created_at);

                        // 2. Safely initialize sender entry in history if it doesn't exist
                        if (!history[senderId]) {
                            history[senderId] = {};
                        }

                        // 3. Assign message text directly to the specific sender object
                        history[senderId][message.created_at] = message.message_text;
                    }
                }
                const clone_sender = user.cloneNode(true),
                    top_text_sender = clone_sender.querySelector('.top'),
                    bottom_text_sender = clone_sender.querySelector('.bottom')
                top_text_sender.textContent = sender
                clone_sender.addEventListener('click', (event)=>{
                    messages.innerHTML = ''
                    const unsorted = history[sender]
                    const dates = Object.keys(unsorted)
                    dates.sort((a,b) => a.localeCompare(b))
                    const sorted = dates.reduce((acc, key)=>{
                        acc[key] = unsorted[key]
                        return acc
                    },{})
                    console.log(sorted)
                    let seen_dates = []
                    for (const [time,message] of Object.entries(sorted)){
                        if (!message) continue
                        const date_and_time = time.split(' ')
                        const messageEl = document.createElement('div'),
                              timeEl = document.createElement('div'),
                              dateEl = document.createElement('div')
                        messageEl.classList.add('message', 'received');
                        messageEl.innerHTML = `
                            <div class="message-text">${escapeHtml(message)}</div>
                        `;
                        if (!seen_dates[-1] || date_and_time[0] !== seen_dates[-1]){
                            dateEl.textContent = date_and_time[0]
                            dateEl.classList.add('date')
                            messages.appendChild(dateEl)
                        } 
                        timeEl.textContent=date_and_time[1]
                        timeEl.classList.add('time')
                        messageEl.appendChild(timeEl)
                        messages.appendChild(messageEl);
                        
                    }
                    messages.scrollTop = messages.scrollHeight;
                })
                users.appendChild(clone_sender)
            }
        })
    }

    top_bar_owner.appendChild(user_choice)
    // linking the above list to the top_bar_owner
    top_bar_owner.addEventListener('click', (event)=>{
        user_choice.showPicker()
    })
}  
 createLists()
// Message/sending handling
input.addEventListener('keydown', async (event) => {
    // Prevent default newline on Enter (allow Shift+Enter for newline)
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        
        const text = input.value.trim();
        if (!text) return;

        input.value = '';

        // 1. Create and append the message DOM element instantly
        const messageEl = document.createElement('div');
        messageEl.classList.add('message', 'received');
        
        messageEl.classList.add( 'status-loading')
        messageEl.innerHTML = `
            <div class="message-text">${escapeHtml(text)}</div>
        `;
        // 1.1 Create and append time
        const now = new Date();

        const hours = now.getHours();       // 0 - 23
        const minutes = now.getMinutes();   // 0 - 59

        const time = document.createElement('div')

        // Example custom format (HH:MM:SS) with leading zeroes
        const formattedTime = [hours, minutes]
        .map(unit => String(unit).padStart(2, '0'))
        .join(':');

        time.textContent=formattedTime
        time.classList.add('time')
        messageEl.appendChild(time)
        messages.appendChild(messageEl);
        messages.scrollTop = messages.scrollHeight;

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
            messageEl.className = 'message status-error';
        }
    }
});

// Helper utility to sanitize html text nodes
function escapeHtml(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}