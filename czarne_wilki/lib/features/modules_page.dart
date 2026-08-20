import 'package:flutter/material.dart';
import '../theme/wolf_theme.dart';

class ModulesPage extends StatelessWidget {
  final bool offline;
  final bool unmasked;
  const ModulesPage({super.key, required this.offline, required this.unmasked});

  static const items = [
    '1 Most Android ↔ desktop TCP :17886',
    '2 Mikrofon ciagly do STOP (bez autostopu)',
    '3 Biblioteka glosow AI',
    '4 Lokalne modele / repo GGUF Ollama',
    '5 Tryb Siec / Offline',
    '6 Czat + generator tekst/obraz/dzwiek/wideo',
    '7 Planer publikacji',
    '8 Autopost AccessibilityService',
    '9 Personalizacja agenta (system prompt)',
    '10 Asystent kodowania',
    '11 Samonaprawa / DexClassLoader',
    '12 Komunikator E2E X25519+AES-GCM',
    '13 Radio spolecznosciowe',
    '14 Historia SQLite',
    '15 RBAC Hetman/Rotmistrz/Towarzysz/Gosc',
    '16 Moderacja tresci',
    '17 Alerty WILKI_ALERT',
    '18 Agent komentarzy',
    '19 Tryb bez maski',
    '20 Tozsamosc + logo husarsko-wilcze',
    '21 Dobrowolne wplaty',
    '22 Wieloagentowy kontroler jakosci',
  ];

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: items.length,
      separatorBuilder: (_, __) => const Divider(color: WolfTheme.red, height: 1),
      itemBuilder: (_, i) => ListTile(
        leading: const Icon(Icons.shield, color: WolfTheme.red),
        title: Text(items[i]),
        subtitle: Text(offline ? 'offline' : 'siec', style: const TextStyle(color: WolfTheme.silver)),
      ),
    );
  }
}
