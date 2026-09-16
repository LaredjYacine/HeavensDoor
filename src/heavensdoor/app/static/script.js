form = document.getElementById('myform');
prompt = document.getElementById('prompt');
form.addEventListener('submit', function(event) {
    event.preventDefault();
const uservalue = prompt.value
    console.log(uservalue);
});
