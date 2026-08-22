import 'package:flutter/material.dart';
import '../core/store.dart';
import '../core/llm.dart';
import '../theme/wolf_theme.dart';

class ChatPage extends StatefulWidget {
  final bool offline;
  final bool unmasked;
  const ChatPage({super.key, required this.offline, required this.unmasked});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final ctl = TextEditingController();
  final store = WolfStore.instance;
  final llm = WolfLlm.instance;

  @override
  Widget build(BuildContext context) {
    final msgs = store.messages;
    return Column(children: [
      Expanded(
        child: ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: msgs.length,
          itemBuilder: (_, i) {
            final m = msgs[i];
            return Align(
              alignment: m.role == 'user' ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                margin: const EdgeInsets.symmetric(vertical: 4),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: m.role == 'user' ? WolfTheme.red.withOpacity(0.25) : WolfTheme.panel,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(m.content),
              ),
            );
          },
        ),
      ),
      Row(children: [
        PopupMenuButton<String>(
          icon: const Icon(Icons.add, color: WolfTheme.red),
          onSelected: (k) => _plus(k),
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'tekst', child: Text('Tekst')),
            PopupMenuItem(value: 'obraz', child: Text('Obraz')),
            PopupMenuItem(value: 'dzwiek', child: Text('Dzwiek')),
            PopupMenuItem(value: 'wideo', child: Text('Wideo')),
          ],
        ),
        Expanded(
          child: TextField(
            controller: ctl,
            decoration: const InputDecoration(hintText: 'Rozkaz…', contentPadding: EdgeInsets.all(12)),
            onSubmitted: (_) => _send(),
          ),
        ),
        IconButton(onPressed: _send, icon: const Icon(Icons.send, color: WolfTheme.red)),
      ]),
    ]);
  }

  void _send() {
    final t = ctl.text.trim();
    if (t.isEmpty) return;
    ctl.clear();
    store.add('user', t);
    store.add('assistant', llm.generate(t, unmasked: widget.unmasked, offline: widget.offline));
    setState(() {});
  }

  void _plus(String k) {
    store.add('system', 'Generator $k — silnik lokalny.');
    setState(() {});
  }
}
