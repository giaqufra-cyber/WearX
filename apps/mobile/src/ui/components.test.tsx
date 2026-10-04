import { act, render, screen, userEvent } from "@testing-library/react-native";
import { type ReactNode, useState } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import {
  Button,
  Checkbox,
  Chip,
  EmptyState,
  PasswordStrength,
  SegmentedControl,
  Sheet,
  StyleTile,
  TextField,
  TOAST_DURATION_MS,
  Toggle,
  ToastProvider,
  useToast,
} from "@/ui";

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };

function Providers({ children }: { children: ReactNode }) {
  return (
    <SafeAreaProvider initialMetrics={metrics}>
      <ToastProvider>{children}</ToastProvider>
    </SafeAreaProvider>
  );
}

describe("Button", () => {
  test("ha ruolo e nome accessibili e risponde alla pressione", async () => {
    const user = userEvent.setup();
    const onPress = jest.fn();
    await render(<Button label="Crea il tuo account" onPress={onPress} />);
    await user.press(screen.getByRole("button", { name: "Crea il tuo account" }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  test("disabilitato non chiama onPress", async () => {
    const user = userEvent.setup();
    const onPress = jest.fn();
    await render(<Button label="Continua" onPress={onPress} disabled />);
    const button = screen.getByRole("button", { name: "Continua" });
    expect(button).toBeDisabled();
    await user.press(button);
    expect(onPress).not.toHaveBeenCalled();
  });

  test("in caricamento è occupato e non premibile", async () => {
    const user = userEvent.setup();
    const onPress = jest.fn();
    await render(<Button label="Pubblica" onPress={onPress} loading />);
    const button = screen.getByRole("button", { name: "Pubblica" });
    expect(button).toBeBusy();
    await user.press(button);
    expect(onPress).not.toHaveBeenCalled();
  });
});

describe("TextField", () => {
  test("si trova per etichetta e riceve il testo", async () => {
    const user = userEvent.setup();
    function Field() {
      const [value, setValue] = useState("");
      return <TextField label="Nickname" prefix="@" value={value} onChangeText={setValue} />;
    }
    await render(<Field />);
    const input = screen.getByLabelText("Nickname");
    await user.type(input, "nico.atelier");
    expect(input).toHaveDisplayValue("nico.atelier");
  });

  test("l'errore viene annunciato e sostituisce l'aiuto", async () => {
    await render(
      <TextField label="Email" value="x" onChangeText={() => undefined} hint="Ti mandiamo un codice" error="Email non valida" />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Email non valida");
    expect(screen.queryByText("Ti mandiamo un codice")).not.toBeOnTheScreen();
  });

  test("password: il pulsante mostra e nasconde il testo", async () => {
    const user = userEvent.setup();
    await render(<TextField label="Password" secure value="Segreta1!" onChangeText={() => undefined} />);
    const input = screen.getByLabelText("Password");
    expect(input).toHaveProp("secureTextEntry", true);
    await user.press(screen.getByRole("button", { name: "Mostra password" }));
    expect(input).toHaveProp("secureTextEntry", false);
    expect(screen.getByRole("button", { name: "Nascondi password" })).toBeOnTheScreen();
  });
});

describe("PasswordStrength", () => {
  test("riporta il punteggio come valore accessibile", async () => {
    await render(<PasswordStrength password="Abcdefgh1!" />);
    const meter = screen.getByRole("progressbar", { name: "Robustezza della password" });
    expect(meter).toHaveAccessibilityValue({ min: 0, max: 4, now: 4, text: "Ottima" });
  });
});

describe("Toggle e Checkbox", () => {
  test("il toggle cambia stato", async () => {
    const user = userEvent.setup();
    function Setting() {
      const [on, setOn] = useState(false);
      return <Toggle label="Nascondi i prezzi" value={on} onValueChange={setOn} />;
    }
    await render(<Setting />);
    const toggle = screen.getByRole("switch", { name: "Nascondi i prezzi" });
    expect(toggle).not.toBeChecked();
    await user.press(toggle);
    expect(toggle).toBeChecked();
  });

  test("la checkbox cambia stato", async () => {
    const user = userEvent.setup();
    function Consent() {
      const [on, setOn] = useState(false);
      return <Checkbox label="Accetto le regole della community" checked={on} onChange={setOn} />;
    }
    await render(<Consent />);
    const box = screen.getByRole("checkbox", { name: "Accetto le regole della community" });
    await user.press(box);
    expect(box).toBeChecked();
  });
});

describe("SegmentedControl", () => {
  test("un solo segmento attivo alla volta", async () => {
    const user = userEvent.setup();
    function Contact() {
      const [mode, setMode] = useState<"email" | "phone">("email");
      return (
        <SegmentedControl
          label="Contatto"
          value={mode}
          onChange={setMode}
          options={[
            { value: "email", label: "Email" },
            { value: "phone", label: "Telefono" },
          ]}
        />
      );
    }
    await render(<Contact />);
    expect(screen.getByRole("radio", { name: "Email" })).toBeChecked();
    await user.press(screen.getByRole("radio", { name: "Telefono" }));
    expect(screen.getByRole("radio", { name: "Telefono" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Email" })).not.toBeChecked();
  });
});

describe("Chip e StyleTile", () => {
  test("la chip selezionata lo dichiara", async () => {
    await render(<Chip label="Old Money" selected onPress={() => undefined} />);
    expect(screen.getByRole("button", { name: "Old Money" })).toBeSelected();
  });

  test("il riquadro stile selezionabile è una casella con nome e descrizione", async () => {
    const user = userEvent.setup();
    const onPress = jest.fn();
    await render(
      <StyleTile name="Jappo" tagline="Tokyo street, layering" tone="#1F2946" selectable selected={false} onPress={onPress} />,
    );
    const tile = screen.getByRole("checkbox", { name: "Jappo. Tokyo street, layering" });
    expect(tile).not.toBeChecked();
    await user.press(tile);
    expect(onPress).toHaveBeenCalled();
  });
});

describe("Toast", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test("appare, viene annunciato e sparisce da solo", async () => {
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    function Voter() {
      const toast = useToast();
      return <Button label="Vota" onPress={() => toast.show("Hai votato 84. Il voto è anonimo.")} />;
    }
    await render(<Voter />, { wrapper: Providers });
    await user.press(screen.getByRole("button", { name: "Vota" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Hai votato 84. Il voto è anonimo.");
    // Il timer aggiorna lo stato: va fatto avanzare dentro act.
    await act(async () => {
      await jest.advanceTimersByTimeAsync(TOAST_DURATION_MS + 50);
    });
    expect(screen.queryByRole("alert")).not.toBeOnTheScreen();
  });

  test("useToast fuori dal provider dà un errore chiaro", async () => {
    const spy = jest.spyOn(console, "error").mockImplementation(() => undefined);
    function Broken() {
      useToast();
      return null;
    }
    await expect(render(<Broken />)).rejects.toThrow("useToast va usato dentro <ToastProvider>");
    spy.mockRestore();
  });
});

describe("Sheet ed EmptyState", () => {
  test("il pannello ha un titolo e si chiude con la X", async () => {
    const user = userEvent.setup();
    const onClose = jest.fn();
    await render(
      <Sheet visible title="Segnala il fit" onClose={onClose}>
        <Button label="Nudità" onPress={() => undefined} />
      </Sheet>,
      { wrapper: Providers },
    );
    expect(screen.getByRole("heading", { name: "Segnala il fit" })).toBeOnTheScreen();
    await user.press(screen.getAllByRole("button", { name: "Chiudi" }).at(-1)!);
    expect(onClose).toHaveBeenCalled();
  });

  test("lo stato vuoto mostra titolo e azione", async () => {
    const onPress = jest.fn();
    await render(<EmptyState title="Nessun fit qui" body="Sii il primo." action={{ label: "Pubblica", onPress }} />);
    expect(screen.getByRole("heading", { name: "Nessun fit qui" })).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Pubblica" })).toBeOnTheScreen();
  });
});
