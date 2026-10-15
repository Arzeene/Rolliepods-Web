<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rolliepods | @yield('title')</title>
    
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@300..700&family=Quicksand:wght@300..700&display=swap" rel="stylesheet">
    
    <!-- Link to CSS -->
    <link rel="stylesheet" href="{{ asset('css/styles.css') }}">
</head>
<body>

    <!-- Shared Header -->
    <header>
        <div class="logo">
          <a href="index.html">
            <img src="img/rolliepods logo RGB-04.png" alt="Rolliepods Logo" class="header-logo">
          </a>
        </div>
        <nav>
            <ul>
                <li><a href="{{ url('/') }}">HOME</a></li>
                <li><a href="{{ url('/about') }}">ABOUT</a></li>
                <li><a href="{{ url('/news') }}">NEWS</a></li>
                <li><a href="{{ url('/contact') }}">CONTACT US</a></li>
                <li><a href="{{ url('/login') }}" class="auth-links">LOGIN | SIGN UP</a></li>
            </ul>
        </nav>
    </header>

    <main>
        @yield('content')
    </main>

    <!-- Shared Footer -->
    <footer>
        <div class="logo"><img src="img/rolliepods logo RGB-04.png" alt="Rolliepods Logo" class="header-logo"></div>
        <div class="contact-info">
            <p>ADB Ave Tower, ADB Ave, Pasig, Philippines, 1605</p>
            <p>rolliepods@gmail.com</p>
        </div>
        <div class="slogan">
            <h3 style="color: var(--lime-green);">Good<br>Spaces,<br>Good<br>People.</h3>
        </div>
    </footer>

</body>
</html>
