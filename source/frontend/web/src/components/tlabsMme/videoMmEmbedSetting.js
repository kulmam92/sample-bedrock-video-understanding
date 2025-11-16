import React, { Component } from 'react';
import { FormField, Input, Select, Container, ColumnLayout, Header, Checkbox, RadioGroup } from '@cloudscape-design/components';

class VideoMmEmbeddingSetting extends Component {

    constructor(props) {
        super(props);
        this.state = {
            request: null,
            mmEmbedModel: "twelvelabs.marengo-embed-2-7-v1:0",

            // Marengo 2.7 settings
            startSec: null,
            lengthSec: null,
            useFixedLengthSec: null,
            minClipSec: null, //Default: 4, Min: 1, Max: 5.
            embedOptionVisualText: true,
            embedOptionVisualImage: true,
            embedOptionAudio: true,

            // Marengo 3.0 settings
            startSec30: null,
            endSec30: null,
            segmentationMethod: "dynamic", // dynamic or fixed
            minDurationSec: 4,
            durationSec: 6,
            embedOption30Visual: true,
            embedOption30Audio: true,
            embedOption30Transcription: true,
            embedScopeClip: true,
            embedScopeAsset: false
        }
    }   

  getRequest() {
    const isMarengo30 = this.props.selectedModelId === "marengo30";

    if (isMarengo30) {
      // Marengo 3.0 format
      var embedOption30 = [];
      if (this.state.embedOption30Visual)
        embedOption30.push("visual");
      if (this.state.embedOption30Audio)
        embedOption30.push("audio");
      if (this.state.embedOption30Transcription)
        embedOption30.push("transcription");

      var embedScope30 = [];
      if (this.state.embedScopeClip)
        embedScope30.push("clip");
      if (this.state.embedScopeAsset)
        embedScope30.push("asset");

      var segmentation = {
        method: this.state.segmentationMethod
      };
      if (this.state.segmentationMethod === "dynamic") {
        segmentation.dynamic = {
          minDurationSec: this.state.minDurationSec
        };
      } else {
        segmentation.fixed = {
          durationSec: this.state.durationSec
        };
      }

      var request = {
        inputType: "video",
        video: {
          segmentation: segmentation
        }
      };

      if (this.state.startSec30 !== null && this.state.startSec30 !== "") {
        request.video.startSec = this.state.startSec30;
      }
      if (this.state.endSec30 !== null && this.state.endSec30 !== "") {
        request.video.endSec = this.state.endSec30;
      }
      if (embedOption30.length > 0) {
        request.video.embeddingOption = embedOption30;
      }
      if (embedScope30.length > 0) {
        request.video.embeddingScope = embedScope30;
      }

      return {
        ModelId: "twelvelabs.marengo-embed-3-0-v1:0",
        TaskType: isMarengo30?"marengo30":"marengo27",
        TLabsRequest: request
      };
    } else {
      // Marengo 2.7 format
      var embedOption = [];
      if (this.state.embedOptionVisualText)
        embedOption.push("visual-text");
      if (this.state.embedOptionVisualImage)
        embedOption.push("visual-image");
      if (this.state.embedOptionAudio)
        embedOption.push("audio");

      var request = {
        inputType: "video",
        embeddingOption: embedOption
      };
      if (this.state.startSec)
        request["startSec"] = this.state.startSec;
      if (this.state.lengthSec)
        request["lengthSec"] = this.state.lengthSec;
      if (this.state.useFixedLengthSec)
        request["useFixedLengthSec"] = this.state.useFixedLengthSec;
      if (this.state.minClipSec)
        request["minClipSec"] = this.state.minClipSec;

      return {
        ModelId: this.state.mmEmbedModel,
        TaskType: "marengo27",
        TLabsRequest: request
      };
    }
  }

  render() {
    const isMarengo30 = this.props.selectedModelId === "marengo30";

    if (isMarengo30) {
      // Marengo 3.0 UI
      return <div className="embedding">
        <Container header={<Header variant='h3'>TwelveLabs Marengo Embed 3.0 Setting</Header>}>
          <ColumnLayout columns={2}>
            <FormField label="Start Second" description="Start offset in seconds from video start. Leave empty to start from beginning.">
              <Input
                onChange={({ detail }) => this.setState({startSec30: detail.value ? parseFloat(detail.value) : null})}
                value={this.state.startSec30 !== null ? this.state.startSec30 : ""}
                inputMode="numeric"
                type="number"
              />
            </FormField>
            
            <FormField label="End Second" description="End offset in seconds from video start. Leave empty to process to the end.">
              <Input
                onChange={({ detail }) => this.setState({endSec30: detail.value ? parseFloat(detail.value) : null})}
                value={this.state.endSec30 !== null ? this.state.endSec30 : ""}
                inputMode="numeric"
                type="number"
              />
            </FormField>
          </ColumnLayout>
          
          <ColumnLayout columns={2}>
            <FormField label="Segmentation Method" description="Choose how to segment the video for embedding.">
              <RadioGroup
                onChange={({ detail }) => this.setState({segmentationMethod: detail.value})}
                value={this.state.segmentationMethod}
                items={[
                  { value: "dynamic", label: "Dynamic", description: "Video is split by shot boundaries with minimum duration" },
                  { value: "fixed", label: "Fixed", description: "Video is split into fixed duration segments" }
                ]}
              />
            </FormField>

            {this.state.segmentationMethod === "dynamic" ? (
              <FormField label="Minimum Duration (seconds)" description="Minimum duration for dynamic segments. Default: 4, Min: 1, Max: 5.">
                <Input
                  onChange={({ detail }) => this.setState({minDurationSec: parseInt(detail.value) || 4})}
                  value={this.state.minDurationSec}
                  inputMode="numeric"
                  type="number"
                />
              </FormField>
            ) : (
              <FormField label="Fixed Duration (seconds)" description="Fixed duration for each segment. Range: 2-10 seconds.">
                <Input
                  onChange={({ detail }) => this.setState({durationSec: parseInt(detail.value) || 6})}
                  value={this.state.durationSec}
                  inputMode="numeric"
                  type="number"
                />
              </FormField>
            )}
          </ColumnLayout>

          <ColumnLayout columns={2}>
            <FormField label="Embedding Options" description="Specifies embedding types: visual, audio, or transcription.">
              <Checkbox 
                onChange={({ detail }) => this.setState({embedOption30Visual: detail.checked})}
                checked={this.state.embedOption30Visual}
              >Visual</Checkbox>
              <Checkbox 
                onChange={({ detail }) => this.setState({embedOption30Audio: detail.checked})}
                checked={this.state.embedOption30Audio}
              >Audio</Checkbox>
              <Checkbox 
                onChange={({ detail }) => this.setState({embedOption30Transcription: detail.checked})}
                checked={this.state.embedOption30Transcription}
              >Transcription</Checkbox>
            </FormField>

            <FormField label="Embedding Scope" description="Optional: Choose clip-level, asset-level, or both.">
              <Checkbox 
                onChange={({ detail }) => this.setState({embedScopeClip: detail.checked})}
                checked={this.state.embedScopeClip}
              >Clip</Checkbox>
              <Checkbox 
                onChange={({ detail }) => this.setState({embedScopeAsset: detail.checked})}
                checked={this.state.embedScopeAsset}
              >Asset</Checkbox>
            </FormField>
          </ColumnLayout>
        </Container>
      </div>;
    } else {
      // Marengo 2.7 UI
      return <div className="embedding">
        <Container header={<Header variant='h3'>TwelveLabs Marengo Embed 2.7 Setting</Header>}>
          <ColumnLayout columns={2}>
            <FormField label="Start Second" description="Start offset in seconds from video start. Leave it empty will start from the beginning.">
              <Input
                onChange={({ detail }) => this.setState({startSec:detail.value})}
                value={parseFloat(this.state.startSec)}
                inputMode="numeric"
                type="number"
              />
            </FormField>
            <FormField label="Length Second" description="The length in seconds of the video where the processing would take from the Start Second. Leave empty to process the video to the end.">
              <Input
                onChange={({ detail }) => this.setState({lengthSec:detail.value})}
                value={parseFloat(this.state.lengthSec)}
                inputMode="numeric"
                type="number"
              />
            </FormField>
          </ColumnLayout>
          <ColumnLayout columns={2}>
            <FormField label="Fix length second" description="Fixed clip duration in seconds (2–10) for embedding. If not set: video is split by shot boundaries.">
              <Input
                onChange={({ detail }) => this.setState({useFixedLengthSec:detail.value})}
                value={parseFloat(this.state.useFixedLengthSec)}
                inputMode="numeric"
                type="number"
              />
            </FormField>
            <FormField label="Minium clip second" description="If a fixed length (in seconds) is specified, it must be greater than this value. Default: 4. Min: 1, Max: 5.">
              <Input
                onChange={({ detail }) => this.setState({minClipSec:detail.value})}
                value={parseInt(this.state.minClipSec)}
                inputMode="numeric"
                type="number"
              />
            </FormField>
          </ColumnLayout>
          <ColumnLayout columns={2}>
            <FormField label="Embedding Options" description="For video only. Specifies embedding types: visual-text, visual-image, or audio.">
              <Checkbox 
                onChange={({ detail }) => this.setState({embedOptionVisualText: detail.checked}) }
                checked={this.state.embedOptionVisualText}
              >visual-text</Checkbox>
              <Checkbox 
                onChange={({ detail }) => this.setState({embedOptionVisualImage: detail.checked}) }
                checked={this.state.embedOptionVisualImage}
              >visual-image</Checkbox>
              <Checkbox 
                onChange={({ detail }) => this.setState({embedOptionAudio: detail.checked}) }
                checked={this.state.embedOptionAudio}
              >audio</Checkbox>
            </FormField>
          </ColumnLayout>
        </Container>
      </div>;
    }
  };
};
export default VideoMmEmbeddingSetting;