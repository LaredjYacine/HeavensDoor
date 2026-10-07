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

    const SolidData = await getResult(Id); // Added missing semicolon
    const streamedData = await getResultStream(Id);

    removeTypingIndicator();

    // Create the assistant message element so we have somewhere to put tokens
    const outputElement = document.createElement('div');
    outputElement.classList.add('message', 'assistant');
    document.getElementById("chat").appendChild(outputElement);

    if (SolidData) {
        cleanPythonString(SolidData);
        addAssistantMessageAnimated(SolidData);
        pinPrompt();
    }

    let fullresponse = '';
    for await (const token of getResultStream(Id)) {
        if (token) {

textStreamer.start(outputElement, token, 10);
            scrollToBottom();
        }
    }
    pinPrompt();

    resetInput(); // Moved inside the async function block properly
});


// We use a helper object or closure to keep track of the active element and queue
const textStreamer = {
    targetElement: null,
    isStreaming: false,
    queue: '',

    async start(element, initialText = '', delayMs = 30) {
        this.targetElement = element;
        this.queue += initialText;

        if (this.isStreaming) return; // If already streaming, just let the loop pick up the new text
        this.isStreaming = true;

        while (this.queue.length > 0) {
            const nextChar = this.queue[0];
            this.queue = this.queue.slice(1);

            this.targetElement.textContent += nextChar;

            // Optional: scrollToBottom();

            await new Promise(resolve => setTimeout(resolve, delayMs));
        }

        this.isStreaming = false;
    },

    // Call this whenever you receive a new word or chunk later
    append(newText) {
        this.queue += newText;
    }
};




function resetInput() {
    Lock = false;
    promptInput.disabled = false;
    promptInput.placeholder = 'Chat with Heaven';
}
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
    try {
        const response = await fetch(
            `${url}/v2/result?job_id=${encodeURIComponent(Id)}`,
            {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            }
        );


        const reader = response.body.getReader();
        console.log("Streaming started", reader);
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const text = decoder.decode(value, { stream: true });
            const lines = text.split('\n');

            for (const line of lines) {
                if (line.startsWith('data:')) {
                    const jsonString = line.replace('data:', '').trim();
                    if (!jsonString) continue;

                    const data = JSON.parse(jsonString);
                    console.log(data['token'])
                    console.log('This is data alone ', data)
                    if (data.done) {
                      yield data.token

                        break;
                    }
                    yield data.token
                }
            }
        }
    } catch (error) {
        console.error(error);
    }
}




async function postprompt(text, idempotency, sessionId) {
    try {
        const idempotencyId = idempotency


        const body = JSON.stringify({'query':text, 'sessionId':sessionId,'idempotency_key':idempotency})

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

async function getResult(Id){
  try {
      const response = await fetch(
          `${url}/v2/result?job_id=${encodeURIComponent(Id)}`,
          {
              method: 'GET',
              headers: {
                  'Content-Type': 'application/json'
              }
          }
      );
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
          const result = await response.json();
          console.log(result.status);

          if (result.status === 'PENDING' || result.status === 'STARTED') {
              await new Promise(resolve => setTimeout(resolve, 1000));
              return await getResult(Id);
          }
          if (result.status === '202 Accepted') {
              return result;
          }
          return result;
      }
      return null
  }
      catch (error){
        console.error(error)
      }
      }
