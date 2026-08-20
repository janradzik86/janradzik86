import 'package:flutter/material.dart';

class WolfTheme {
  static const black = Color(0xFF080808);
  static const panel = Color(0xFF161618);
  static const red = Color(0xFFE3242B);
  static const white = Color(0xFFF5F5F5);
  static const silver = Color(0xFFBABABE);

  static ThemeData get dark => ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: black,
        colorScheme: const ColorScheme.dark(
          primary: red,
          secondary: white,
          surface: panel,
        ),
        appBarTheme: const AppBarTheme(backgroundColor: black, foregroundColor: white),
        useMaterial3: true,
      );
}
