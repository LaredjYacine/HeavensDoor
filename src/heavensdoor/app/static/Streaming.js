const form = document.getElementById('myform');
const promptInput = document.getElementById('prompt');
// Goal is to clean the code my self NO AI it will fail me Fix the STream process and Stream APi
const url = window.BACKEND_URL;
let Lock = false;
let sessionId = localStorage.getItem("chat_session_id");
if (!sessionId) {
    sessionId = crypto.randomUUID(); // Generate a unique session ID
    localStorage.setItem("chat_session_id", sessionId);
}
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

    const Id = await postprompt(query, null, sessionId);
    promptInput.value = '';
    promptInput.style.height = 'auto';
    console.log('_Id', Id);
    if (!Id) {
        resetInput();
        removeTypingIndicator();
        return;
    }

    // Create the assistant message element so we have somewhere to put tokens

    let fullresponse = '';
    let outputElement = null;
    for await (const token of getResultStream(Id)) {
        if (!token || token === '[DONE]') {continue}
          if(!outputElement){
            removeTypingIndicator();
            outputElement = document.createElement('div');
            outputElement.classList.add('message', 'assistant');
            document.getElementById("chat").appendChild(outputElement);
          }
          fullresponse+= token


          textStreamer.start(outputElement, token, 10);

          scrollToBottom();

    }
    await textStreamer.waitUntilFinished();
    if (outputElement) {
        outputElement.innerHTML = marked.parse(fullresponse);
    }
    pinPrompt();
    removeTypingIndicator();

    resetInput();
});


const textStreamer = {
    targetElement: null,
    isStreaming: false,
    queue: '',
    resolveFinished: null,
    rawAccumulated: '',
    chunk: '',

    async start(element, initialText = '', delayMs = 30) {
        this.targetElement = element;
        this.queue += initialText;

        if (this.isStreaming) return;

        this.isStreaming = true;

        while (this.queue.length > 0) {
            const nextChar = this.queue[0];
            this.queue = this.queue.slice(1);

            this.chunk += nextChar;
            this.rawAccumulated += nextChar;

            console.log('Accumulated words:', this.rawAccumulated);

            // Check if chunk contains at least 1 clean word
            const words = getCleanWords(this.chunk);

            if (words && words.length > 0) {
                // Parse markdown and update DOM
                this.targetElement.innerHTML = marked.parse(this.rawAccumulated);
                this.chunk = ''; // Reset word buffer
            } else {
                // For non-word chars (like spaces/punctuation), render raw text smoothly without wiping HTML
                this.targetElement.innerHTML = marked.parse(this.rawAccumulated);
            }

            await new Promise(resolve => setTimeout(resolve, delayMs));
        }

        if (this.targetElement && this.rawAccumulated) {
            this.targetElement.innerHTML = marked.parse(this.rawAccumulated);
        }

        this.isStreaming = false;

        if (this.resolveFinished) {
            this.resolveFinished();
            this.resolveFinished = null;
        }
    },

    append(newText) {
        this.queue += newText;
    },

    waitUntilFinished() {
        if (!this.isStreaming && this.queue.length === 0) {
            return Promise.resolve();
        }

        return new Promise(resolve => {
            this.resolveFinished = resolve;
        });
    }
};

function getCleanWords(text) {
  const words =  text.match(/\b[a-zA-Z0-9']+\b/g) || [];
  return words.length >= 1;
}
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


function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
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


function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}



async function* getResultStream(Id) {
    const decoder = new TextDecoder();
    let buffer = '';
    let polls = 0;
    const maxPolls = 180;

    while (polls < maxPolls) {
        polls++;
        const response = await fetch(
            `${url}/v2/result?job_id=${encodeURIComponent(Id)}`,
            {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            }
        );

        const contentType = response.headers.get('content-type') || '';

        if (contentType.includes('application/json')) {
            const result = await response.json();

            if (result.status === 'PENDING' || result.status === 'STARTED') {
                await new Promise(resolve => setTimeout(resolve, 1000));
                continue;
            }
            if (result.status === '202 Accepted' && result.result) {
                yield result.result;
            }
            return;
        }

        const reader = response.body.getReader();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            let newlineIndex;
            while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
                const line = buffer.slice(0, newlineIndex);
                buffer = buffer.slice(newlineIndex + 1);

                if (!line.startsWith('data:')) continue;

                const jsonString = line.replace('data:', '').trim();
                if (!jsonString) continue;

                let data;
                try {
                    data = JSON.parse(jsonString);
                } catch (error) {
                    console.error(error);
                    continue;
                }

                if (data.done) {
                    yield data.token;
                    return;
                }
                yield data.token;
            }
        }
        return;
    }
}




async function postprompt(text, idempotency, sessionId) {
    try {
        const idempotencyId = idempotency


        const body = JSON.stringify({'query':text, 'session_id':sessionId,'idempotency_key':idempotency})

        const response = await fetch(
            `${url}/v2/agent`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: body
            }
        );

        if (!response.ok) {
            throw new Error(`Couldn't post the prompt: ${response.status}`);
        }
        const post_response = await response.json();

        if (post_response && post_response.Status === '202 Accepted') {
          return post_response.job_id;
        }
        return null;
    } catch (error) {
        console.error(error);
        return null;
    }
}

function addUserMessage(text) {
    const chat = document.getElementById('chat');

    const message = document.createElement('div');
    message.classList.add('message', 'User');
    message.textContent = text;

    chat.appendChild(message);
    scrollToBottom();
}
