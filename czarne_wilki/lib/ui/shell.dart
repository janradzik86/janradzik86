import 'package:flutter/material.dart';
import '../theme/wolf_theme.dart';
import '../features/chat_page.dart';
import '../features/modules_page.dart';

class WolfShell extends StatefulWidget {
  const WolfShell({super.key});
  @override
  State<WolfShell> createState() => _WolfShellState();
}

class _WolfShellState extends State<WolfShell> {
  int idx = 0;
  bool offline = true;
  bool unmasked = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(children: [
          Image.asset('assets/logo.png', width: 36, height: 36),
          const SizedBox(width: 10),
          const Flexible(
            child: Text('Czarne Wilki Prawdy – Wszyscy Won!', overflow: TextOverflow.ellipsis),
          ),
        ]),
        actions: [
          TextButton(
            onPressed: () => setState(() => offline = !offline),
            child: Text(offline ? 'OFFLINE' : 'SIEC', style: const TextStyle(color: WolfTheme.red)),
          ),
          TextButton(
            onPressed: () => setState(() => unmasked = !unmasked),
            child: Text(unmasked ? 'BEZ MASKI' : 'MASKA', style: const TextStyle(color: WolfTheme.white)),
          ),
        ],
      ),
      body: idx == 0
          ? ChatPage(offline: offline, unmasked: unmasked)
          : ModulesPage(offline: offline, unmasked: unmasked),
      bottomNavigationBar: NavigationBar(
        selectedIndex: idx,
        onDestinationSelected: (i) => setState(() => idx = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.forum), label: 'Czat'),
          NavigationDestination(icon: Icon(Icons.hub), label: '22 moduly'),
        ],
      ),
    );
  }
}
