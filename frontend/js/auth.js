async function ensureToken(){
let token =
localStorage.getItem(
"token"
);
if(token){
return token;
}
const data =
await apiFetch(
"/api/token"
);
token =
data.data.token;
localStorage.setItem(
"token",
token
);
return token;
}
