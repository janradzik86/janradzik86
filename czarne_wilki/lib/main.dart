import 'package:flutter/material.dart';
import 'theme/wolf_theme.dart';
import 'ui/shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const WolfApp());
}

class WolfApp extends StatelessWidget {
  const WolfApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Czarne Wilki Prawdy – Wszyscy Won!',
      debugShowCheckedModeBanner: false,
      theme: WolfTheme.dark,
      home: const SplashGate(),
    );
  }
}

class SplashGate extends StatefulWidget {
  const SplashGate({super.key});
  @override
  State<SplashGate> createState() => _SplashGateState();
}

class _SplashGateState extends State<SplashGate> {
  @override
  void initState() {
    super.initState();
    Future.delayed(const Duration(milliseconds: 2200), () {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          pageBuilder: (_, __, ___) => const WolfShell(),
          transitionsBuilder: (_, a, __, c) => FadeTransition(opacity: a, child: c),
        ),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF080808),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image(image: AssetImage('assets/logo.png'), width: 280, height: 280),
            SizedBox(height: 24),
            Text(
              'Czarne Wilki Prawdy – Wszyscy Won!',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    );
  }
}
