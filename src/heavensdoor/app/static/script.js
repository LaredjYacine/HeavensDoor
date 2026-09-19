const form = document.getElementById('myform');
const promptInput = document.getElementById('prompt');

const url = window.BACKEND_URL;
let Lock = false;

promptInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});

function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (Lock) return;

    const query = promptInput.value.trim();
    if (!query) return;

    Lock = true;
    promptInput.disabled = true;
    promptInput.placeholder = 'Heaven is thinking...';

    addUserMessage(query);
    addTypingIndicator();
    scrollToBottom();

    const Id = await postprompt(query);
    promptInput.value = '';
    promptInput.style.height = 'auto';

    if (!Id) {
        removeTypingIndicator();
        resetInput();
        return;
    }

    const data = await getResult(Id);

    removeTypingIndicator();

    if (data && data.result) {
        const cleanedText = cleanPythonString(data.result);
        await addAssistantMessageAnimated(cleanedText);
        pinPrompt();
    }

    resetInput();
});

function resetInput() {
    Lock = false;
    promptInput.disabled = false;
    promptInput.placeholder = 'Chat with Heaven';
}

function pinPrompt() {
    const element = document.querySelector('.user_prompt');
    element.style.cssText = `
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        justify-content: center;
        z-index: 1000;
    `;
    element.style.textAlign = '';
}

// ---- Message rendering ----
function addUserMessage(text) {
    const chat = document.getElementById('chat');

    const message = document.createElement('div');
    message.classList.add('message', 'User');
    message.textContent = text;

    chat.appendChild(message);
    scrollToBottom();
}

function addTypingIndicator() {
    const chat = document.getElementById('chat');

    const message = document.createElement('div');
    message.classList.add('message', 'assistant', 'typing-indicator');
    message.id = 'typing-indicator';
    message.innerHTML = '<span></span><span></span><span></span>';

    chat.appendChild(message);
    scrollToBottom();
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

async function addAssistantMessageAnimated(text) {
    const chat = document.getElementById('chat');

    const message = document.createElement('div');
    message.classList.add('message', 'assistant');
    chat.appendChild(message);

    let currentText = '';
    let index = 0;
    const step = 5;
    const speed = 4;

    return new Promise((resolve) => {
        tick(0);

        function tick() {
            if (index >= text.length) {
                resolve();
                return;
            }
            const next = Math.min(index + step, text.length);
            currentText = text.slice(0, next);
            message.innerHTML = marked.parse(currentText);
            scrollToBottom();
            index = next;
            setTimeout(tick, speed);
        }
    });
}

// ---- Clean the Python-tuple artifact from the agent response ----
function cleanPythonString(rawStr) {
    if (!rawStr) return '';
    let cleaned = rawStr.trim();

    // 1. Remove a leading '(' and any starting quote
    if (cleaned.startsWith('(')) {
        cleaned = cleaned.substring(1).trim();
    }
    if (cleaned.startsWith("'") || cleaned.startsWith('"')) {
        cleaned = cleaned.substring(1);
    }

    // 2. Remove trailing Python tuple artifacts like '),', '),''', or just ')'
    cleaned = cleaned.replace(/\s*\),\s*['"]*$/, '');
    cleaned = cleaned.replace(/\s*\)\s*$/, '');

    // 3. Remove a trailing quote left hanging from the wrapper
    if ((cleaned.endsWith("'") || cleaned.endsWith('"')) && !cleaned.endsWith("\\'")) {
        cleaned = cleaned.substring(0, cleaned.length - 1);
    }

    // 4. Split by newlines and unquote individual Python string pieces
    const lines = cleaned.split('\n');
    const finalParts = [];

    for (let line of lines) {
        line = line.trim();
        if (line.startsWith("'") && line.endsWith("'")) {
            finalParts.push(line.slice(1, -1));
        } else {
            finalParts.push(line);
        }
    }

    // 5. Join pieces back and convert literal escaped '\n' into real line breaks
    const joined = finalParts.join('');
    return joined.replace(/\\n/g, '\n').trim();
}

// ---- Polling ----
async function getResult(Id) {
    try {
        const response = await fetch(
            `${url}/result?job_id=${encodeURIComponent(Id)}`,
            {
                method: 'GET',
                headers: {
                    'accept': '*/*'
                }
            }
        );

        if (!response.ok) {
            throw new Error(`Couldn't fetch the data: ${response.status}`);
        }

        const result = await response.json();

        if (result.state === 'PENDING' || result.state === 'STARTED') {
            await new Promise(resolve => setTimeout(resolve, 1000));
            return await getResult(Id);
        }

        return result;
    } catch (error) {
        console.error(error);
    }
}

async function postprompt(text, idempotency) {
    try {
        const idempotencyId = idempotency
            || (crypto.randomUUID && crypto.randomUUID())
            || ('id-' + Date.now() + '-' + Math.random().toString(36).slice(2));
        const body = `?query=${encodeURIComponent(text)}&idempotency_id=${encodeURIComponent(idempotencyId)}`;

        const response = await fetch(
            `${url}/agent${body}`,
            {
                method: 'POST',
                headers: {
                    'accept': '*/*'
                }
            }
        );

        if (!response.ok) {
            throw new Error(`Couldn't post the prompt: ${response.status}`);
        }
        const post_response = await response.json();

        if (post_response && post_response.status === '202 Accepted') {
            return post_response.job_id;
        }
        return null;
    } catch (error) {
        console.error(error);
        return null;
    }
}