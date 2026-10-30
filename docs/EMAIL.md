# Email di accesso in italiano e inglese

Le email di conferma e di recupero password le manda **Supabase Auth**, non l'API: i testi si
incollano nel progetto Supabase (Dashboard → Authentication → Emails → Templates), uno per
ambiente (staging e produzione).

Dalla seduta 34 l'app scrive la lingua nei dati dell'account (`user_metadata.lang`, "it" o
"en"): alla registrazione e ogni volta che la lingua dell'app cambia. Nei modelli Supabase quei
dati sono `{{ .Data }}`, quindi lo stesso modello sceglie la lingua da solo. Senza lingua
(account creati prima della seduta 34) vale l'italiano.

L'oggetto dell'email è uno solo per modello: lo teniamo in tutte e due le lingue.

## Conferma della registrazione ("Confirm signup")

Oggetto: `Il tuo codice WearX · Your WearX code`

```html
{{ if eq .Data.lang "en" }}
<h2>Welcome to WearX</h2>
<p>Your confirmation code is:</p>
<p style="font-size:28px;letter-spacing:6px"><strong>{{ .Token }}</strong></p>
<p>Type it in the app to finish signing up. The code expires in 1 hour.</p>
<p>If you didn't sign up for WearX, you can ignore this email.</p>
{{ else }}
<h2>Benvenuto su WearX</h2>
<p>Il tuo codice di conferma è:</p>
<p style="font-size:28px;letter-spacing:6px"><strong>{{ .Token }}</strong></p>
<p>Scrivilo nell'app per finire la registrazione. Il codice scade tra 1 ora.</p>
<p>Se non ti sei registrato su WearX, ignora questa email.</p>
{{ end }}
```

## Recupero della password ("Reset password")

Oggetto: `Nuova password WearX · New WearX password`

```html
{{ if eq .Data.lang "en" }}
<h2>Choose a new password</h2>
<p>Your code is:</p>
<p style="font-size:28px;letter-spacing:6px"><strong>{{ .Token }}</strong></p>
<p>Type it in the app, then choose the new password. The code expires in 1 hour.</p>
<p>If you didn't ask for it, ignore this email: your password stays the same.</p>
{{ else }}
<h2>Scegli una nuova password</h2>
<p>Il tuo codice è:</p>
<p style="font-size:28px;letter-spacing:6px"><strong>{{ .Token }}</strong></p>
<p>Scrivilo nell'app e poi scegli la nuova password. Il codice scade tra 1 ora.</p>
<p>Se non l'hai chiesto tu, ignora questa email: la password resta quella di prima.</p>
{{ end }}
```

## SMS (registrazione con il numero di telefono)

Il modello SMS di Supabase è uno solo e corto: lo teniamo in tutte e due le lingue.

```
WearX: il tuo codice è {{ .Code }} · your code is {{ .Code }}
```

## Come provarlo

1. Incolla i modelli nello staging.
2. Nell'app scegli **English** in Privacy e sicurezza → Lingua · Language.
3. Esci e usa "Password dimenticata" ("Forgot password"): l'email arriva in inglese.
