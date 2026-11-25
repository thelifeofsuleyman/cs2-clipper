// WASAPI process loopback. The parent receives PCM over an anonymous pipe.
// See Microsoft's ApplicationLoopback sample for the process activation API.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <audioclientactivationparams.h>
#include <wrl.h>
#include <cstdint>
#include <cstdio>
#include <cwchar>

using Microsoft::WRL::ComPtr;

class Handle {
public:
    explicit Handle(HANDLE value) : value(value) {}
    ~Handle() { if (value) CloseHandle(value); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    HANDLE value;
};

class Activation final : public Microsoft::WRL::RuntimeClass<
    Microsoft::WRL::RuntimeClassFlags<Microsoft::WRL::ClassicCom>,
    IActivateAudioInterfaceCompletionHandler, Microsoft::WRL::FtmBase> {
public:
    HRESULT STDMETHODCALLTYPE ActivateCompleted(IActivateAudioInterfaceAsyncOperation* operation) override {
        HRESULT activated = E_FAIL;
        ComPtr<IUnknown> object;
        result = operation->GetActivateResult(&activated, &object);
        if (SUCCEEDED(result)) result = activated;
        if (SUCCEEDED(result)) result = object.As(&client);
        SetEvent(ready.value);
        return S_OK;
    }

    Handle ready{CreateEventW(nullptr, FALSE, FALSE, nullptr)};
    HRESULT result = E_FAIL;
    ComPtr<IAudioClient> client;
};

#pragma pack(push, 1)
struct Packet {
    uint64_t timestamp;
    uint32_t bytes;
};
#pragma pack(pop)
static_assert(sizeof(Packet) == 12);

static bool write_pipe(HANDLE pipe, const void* data, DWORD size) {
    auto cursor = static_cast<const BYTE*>(data);
    while (size > 0) {
        DWORD written = 0;
        if (!WriteFile(pipe, cursor, size, &written, nullptr) || written == 0) return false;
        cursor += written;
        size -= written;
    }
    return true;
}

static HRESULT capture(DWORD target_pid, DWORD parent_pid) {
    const Handle target(OpenProcess(SYNCHRONIZE, FALSE, target_pid));
    const Handle parent(OpenProcess(SYNCHRONIZE, FALSE, parent_pid));
    const Handle packets(CreateEventW(nullptr, FALSE, FALSE, nullptr));
    auto activation = Microsoft::WRL::Make<Activation>();
    if (!target.value || !parent.value || !packets.value) return HRESULT_FROM_WIN32(ERROR_INVALID_HANDLE);
    if (!activation || !activation->ready.value) return E_OUTOFMEMORY;

    AUDIOCLIENT_ACTIVATION_PARAMS selection{};
    selection.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
    selection.ProcessLoopbackParams.TargetProcessId = target_pid;
    selection.ProcessLoopbackParams.ProcessLoopbackMode = PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;
    PROPVARIANT arguments{};
    arguments.vt = VT_BLOB;
    arguments.blob.cbSize = sizeof(selection);
    arguments.blob.pBlobData = reinterpret_cast<BYTE*>(&selection);
    ComPtr<IActivateAudioInterfaceAsyncOperation> operation;
    HRESULT result = ActivateAudioInterfaceAsync(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK, __uuidof(IAudioClient),
                                                 &arguments, activation.Get(), &operation);
    if (FAILED(result)) return result;
    const HANDLE startup[] = {parent.value, target.value, activation->ready.value};
    const DWORD arrived = WaitForMultipleObjects(ARRAYSIZE(startup), startup, FALSE, 5000);
    if (arrived != WAIT_OBJECT_0 + 2) return HRESULT_FROM_WIN32(ERROR_OPERATION_ABORTED);
    if (FAILED(activation->result)) return activation->result;

    auto client = activation->client;
    WAVEFORMATEX format{WAVE_FORMAT_PCM, 2, 44100, 176400, 4, 16, 0};
    constexpr DWORD flags = AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK |
                            AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM;
    result = client->Initialize(AUDCLNT_SHAREMODE_SHARED, flags, 0, 0, &format, nullptr);
    if (FAILED(result)) return result;
    result = client->SetEventHandle(packets.value);
    if (FAILED(result)) return result;
    ComPtr<IAudioCaptureClient> reader;
    result = client->GetService(IID_PPV_ARGS(&reader));
    if (FAILED(result)) return result;
    result = client->Start();
    if (FAILED(result)) return result;

    const auto output = GetStdHandle(STD_OUTPUT_HANDLE);
    const Packet started{};
    const HANDLE running[] = {parent.value, target.value, packets.value};
    bool connected = write_pipe(output, &started, sizeof(started));
    while (connected && WaitForMultipleObjects(ARRAYSIZE(running), running, FALSE, INFINITE) == WAIT_OBJECT_0 + 2) {
        UINT32 next = 0;
        while (connected && SUCCEEDED(result = reader->GetNextPacketSize(&next)) && next > 0) {
            BYTE* data = nullptr;
            UINT32 frames = 0;
            DWORD status = 0;
            UINT64 stamp = 0;
            result = reader->GetBuffer(&data, &frames, &status, nullptr, &stamp);
            if (FAILED(result) || frames == 0) break;
            // Gaps are filled by the parent. Sending silence repeatedly wastes memory.
            if (data && !(status & AUDCLNT_BUFFERFLAGS_SILENT)) {
                if (status & AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR) stamp = 0;
                const Packet packet{stamp, frames * format.nBlockAlign};
                connected = write_pipe(output, &packet, sizeof(packet)) &&
                            write_pipe(output, data, packet.bytes);
            }
            result = reader->ReleaseBuffer(frames);
            if (FAILED(result)) break;
        }
        if (FAILED(result)) break;
    }
    client->Stop();
    return result;
}

static DWORD parse_pid(const wchar_t* value) {
    wchar_t* end = nullptr;
    const auto pid = wcstoul(value, &end, 10);
    return *value && !*end ? pid : 0;
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) return 2;
    const DWORD target = parse_pid(argv[1]);
    const DWORD parent = parse_pid(argv[2]);
    if (!target || !parent) return 2;
    HRESULT result = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (SUCCEEDED(result)) {
        result = capture(target, parent);
        CoUninitialize();
    }
    if (FAILED(result)) {
        std::fprintf(stderr, "WASAPI process capture failed (0x%08lX)\n", static_cast<unsigned long>(result));
        return 1;
    }
    return 0;
}
