# Mi Cartera — dashboard personal (móvil)

Dashboard privado de cartera de inversión que corre **enteramente en el
navegador** (Streamlit compilado a WebAssembly con [stlite](https://stlite.net/)),
sin servidor.

Los datos financieros van en `cartera_movil.enc`, **cifrados con AES-256-GCM**.
La app pide una contraseña al abrirse y descifra en el propio navegador
(WebCrypto). Sin la contraseña no hay nada legible aquí: el fichero cifrado es
ruido sin la clave.

Publicado como web estática en GitHub Pages y usado desde el iPhone como app
(Safari → "Añadir a pantalla de inicio").
