import React, { Component } from 'react';
import { Container, FormField, Popover, Header, Toggle, ColumnLayout, Select, Input, Box, ExpandableSection, RadioGroup, Link } from '@cloudscape-design/components';
import VideoFramePromptConfig from './videoFramePromptConfig';
import FrameBasedConfig from '../../resources/frame-based-config.json'
import './videoFrameSampleSetting.css'

class VideoFrameSampleSetting extends Component {

    constructor(props) {
        super(props);
        this.state = {
            request: {},
            enableAudio: true,
            enableSmartSample: true,
            customInternvalOption: {label: "1 frame per second", value:"1"},
            smartSampleThreshold: FrameBasedConfig.image_similarity_threshold_default_novamme,
            similarityMethod: "novamme",

            // frame level
            enableFrameAnalysis: true,
            frameConfigs: null,
            
        };
        this.framePromptConfigRef = React.createRef();
        this.shotPromptConfigRef = React.createRef();
    }   

  getRequest() {
    var frameConfigs = null, shotConfigs = null, warns = [];
    if (this.state.enableFrameAnalysis && this.framePromptConfigRef?.current) {
        frameConfigs = this.framePromptConfigRef.current.getConfigs();
    }
    if (this.state.enableShotAnalysis && this.shotPromptConfigRef?.current) {
        shotConfigs = this.shotPromptConfigRef.current.getConfigs();
    }

    if (frameConfigs?.warnings?.length > 0 || shotConfigs?.warnings?.length > 0)
        return null;

    this.setState({frameConfigs: frameConfigs, shotConfigs: shotConfigs});

    return {
        "PreProcessSetting": {
            "SampleMode": "even",
            "SampleIntervalS": parseFloat(this.state.customInternvalOption.value),
            "SmartSample": this.state.enableSmartSample,
            "SimilarityMethod": this.state.similarityMethod, // "orb" or "novamme"
            "SimilarityThreshold": this.state.enableSmartSample?parseFloat(this.state.smartSampleThreshold):null
        },
        "ExtractionSetting": {
            "Audio": {
                "Transcription": this.state.enableAudio
            },
            "Vision": {
                "Frame": {
                    "Enabled": this.state.enableFrameAnalysis,
                    "PromptConfigs": frameConfigs?.configs,
                }
            }
        }
    }
  }

  render() {
    return <div className='setting'>
              <Container header={<Header variant='h2'>Audio Setting</Header>}>
                  <Toggle
                      onChange={({ detail }) =>
                          this.setState({enableAudio: detail.checked})
                      }
                      checked={this.state.enableAudio}
                      >
                      Transcribe audio (with subtitle) using Amazon Transcribe
                  </Toggle>
              </Container>
              <br/>
              <Container 
                header={<Header variant='h2'>Sample Frames from Video</Header>}
                footer={
                  <ExpandableSection
                    header="Remove similiar images"
                    variant="footer"
                    >
                      <ColumnLayout columns={3}>
                        <div>
                            <Toggle checked={this.state.enableSmartSample} onChange={(e)=>
                                {
                                    this.setState({enableSmartSample: e.detail.checked, enableShotSceneDetection: e.detail.checked});
                                }}>
                            Enable smart sampling
                            </Toggle>
                            <div className='desc'>Remove similiar images</div>
                        </div>
                        <div>
                            <b>Choose similarity calculation method</b>
                            <br/>
                            <RadioGroup
                                onChange={({ detail }) => {this.setState({
                                    similarityMethod: detail.value,
                                    smartSampleThreshold: detail.value === "orb"?FrameBasedConfig.image_similarity_threshold_default_orb: FrameBasedConfig.image_similarity_threshold_default_novamme,
                                    shotSimilarityThreshold: detail.value === "orb"?FrameBasedConfig.shot_similarity_threshold_default_orb: FrameBasedConfig.shot_similarity_threshold_default_novamme
                                })}}
                                value={this.state.similarityMethod}
                                items={[
                                    { value: "novamme", label: "Nova MME", description: "Nova Image Multimodal Embedding + FAISS" },
                                    { value: "orb", label: "ORB", description: "ORB (Oriented FAST and Rotated BRIEF)" },
                                ]}
                            ></RadioGroup>
                        </div>
                        {this.state.enableSmartSample && <FormField
                            label="Smart sampling threshold"
                            info={<Popover
                                header="Compare the computed similarity score against the threshold to determine whether the image should be dropped."
                                content=" For ORB, images with a score greater than the threshold will be dropped. For Nova MME, images with a score lower than the threshold will be dropped."
                                >
                                    <Link>Info</Link>
                            </Popover>}
                            stretch={true}
                        >

                            <Input value={this.state.smartSampleThreshold} inputMode="numeric" type='number' onChange={
                                    ({detail})=>{
                                            this.setState({
                                                smartSampleThreshold: detail.value,
                                            });
                                    }                                                
                                }></Input>
                        </FormField>}
                      </ColumnLayout>
                  </ExpandableSection>
                }
              >
                  <ColumnLayout columns={1}>
                      <FormField
                          label="Select a sample interval"
                          description="Number of frames sampled per second. For example, 2 means sample one frame every two seconds, 0.5 means sample 2 frames per second."
                          >
                          <Select selectedOption={this.state.customInternvalOption}
                              onChange={({ detail }) => {
                                  this.setState({customInternvalOption: detail.selectedOption});
                              }}
                              options={FrameBasedConfig.video_sample_interval}
                              />
                      </FormField>
                      
                  </ColumnLayout>
                </Container>
                <br/>
                <Container header={
                    <Header variant='h2' description="For each frame, apply analysis using your chosen image understanding FM model, prompt, and configurations">Analyze Frames</Header>
                }>
                    <div className='frametoggle'>
                        <Toggle onChange={({ detail }) => {
                                    this.setState({enableFrameAnalysis: detail.checked});
                                }
                            }
                            checked={this.state.enableFrameAnalysis}
                            >
                            Enable Frame Analysis
                        </Toggle>
                    </div>
                    {this.state.enableFrameAnalysis &&
                        <div>
                            <VideoFramePromptConfig 
                                selectedPromptId="frame_summary"
                                sampleConfigs={FrameBasedConfig.frame_prompts}
                                ref={this.framePromptConfigRef}
                                models={FrameBasedConfig.models}
                                promptConfigs={this.state.frameConfigs}
                            />
                        </div>
                    }
              </Container>

    </div>

  };
};
export default VideoFrameSampleSetting;