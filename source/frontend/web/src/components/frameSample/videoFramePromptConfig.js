import React, { Component } from 'react';
import { ButtonDropdown, ColumnLayout, Textarea, Button, Slider, Table, Select, Input, Box, SpaceBetween, Form, ExpandableSection, Container, Header } from '@cloudscape-design/components';
import FrameBasedConfig from '../../resources/frame-based-config.json'
import './videoFramePromptConfig.css';

class VideoFramePromptConfig extends Component {

    constructor(props) {
        super(props);
        this.state = {
            warnings: [],
            configs: [],
            
            // Current editing
            showEditConfig: true,
            name: null,
            selectedPromptId: null,
            modelIdOption: null,
            prompt: null,
            toolConfig: null,

            sampleConfigs: [],
            models: [],

            maxTokens: FrameBasedConfig.default_max_tokens,
            topP: FrameBasedConfig.default_top_p,
            temperature: FrameBasedConfig.default_temperature
        }
    }   

    getConfigs() {
        var configs = this.state.configs;
        var warns = [];
        if (this.state.showEditConfig === true) {
            // Add and validate the last input
            var result = this.constructConfig();
            warns = result.warnings;
            if (warns.length === 0) {
                configs.push(result.config);
                this.setState({configs: configs});
            }
        }

        // remove id field
        configs = configs.map(({ id, ...rest }) => rest);
        return {
            configs: configs,
            warnings: warns
        };
    }

    constructConfig() {

        var warns = [];
        if (this.state.name === null || this.state.name.length === 0) warns.push("Please input a name");
        if (this.state.prompt === null || this.state.prompt.length === 0) warns.push("Please input a prompt");

        // Check if name already exists
        if (this.state.configs && this.state.configs.find(c=>c.name == this.state.name)) {
            warns.push("Name already exists");
        }
        // Check if toolConfig is a valid JSON
        var config = null;
        if (this.state.toolConfig) {
            try {
                config = JSON.parse(this.state.toolConfig);
            } catch (e) {
                warns.push("Tool Configruation is not in valid JSON format");
            }
        }

        this.setState({warnings: warns});

        return {
            config:{
                id: crypto.randomUUID(),
                name: this.state.name,
                modelId: this.state.modelIdOption.value,
                prompt: this.state.prompt,
                toolConfig: config,
                inferConfig: {
                    maxTokens: this.state.maxTokens,
                    topP: this.state.topP,
                    temperature: this.state.temperature
                }
            }, 
            warnings: warns
        };
    }

    async componentDidMount() {
        const { selectedPromptId, sampleConfigs, models, promptConfigs } = this.props;
        this.setState({
            selectedPromptId: selectedPromptId?selectedPromptId : "default",
            sampleConfigs: sampleConfigs,
            models: models,
        },() => {
                this.setState({
                    modelIdOption: this.constructModelOption(models[0].value),
                    configs: promptConfigs?promptConfigs:[]
                });
                this.setFramePrompt(selectedPromptId);
            }
        );

        if (selectedPromptId) {
            
        }
    }

    constructModelOption(model_id) {
        const model = this.state.models.find(item => item.value === model_id);
        if (model)
            return {label: model.name, value: model.value};
        return null;
    }

    setFramePrompt(prompt_id) {
        const prompt = this.state.sampleConfigs.find(item=>item.id == prompt_id);
        if (prompt) {
            this.setState({
                selectedPromptId: prompt.id,
                name: prompt.name,
                modelIdOption: this.constructModelOption(prompt.model_id),
                prompt: prompt.prompt,
                toolConfig: prompt.toolConfig?JSON.stringify(prompt.toolConfig, null, 4):null
            })
        }
        return null;
    }

  render() {
    return  <div className="promptconfig">
        {this.state.configs?.length > 0  &&
                <div>
                    <Table
                        renderAriaLive={({
                            firstIndex,
                            lastIndex,
                            totalItemsCount
                        }) =>
                            `Displaying items ${firstIndex} to ${lastIndex} of ${totalItemsCount}`
                        }
                        columnDefinitions={[
                            {
                                id: "name",
                                header: "Name",
                                cell: item => item.name || "-",
                                sortingField: "name",
                                isRowHeader: true,
                            },
                            {
                                id: "modelId",
                                header: "Model Id",
                                cell: item => item.modelId || "-",
                                sortingField: "modelId"
                            }
                            ,
                            {
                                id: "action",
                                header: "",
                                cell: item => (
                                    <div>
                                    <Button iconName="edit" onClick={()=>{
                                        // Edit prompt config
                                        this.setState({
                                            name: item.name,
                                            prompt: item.prompt,
                                            toolConfig: item.toolConfig? JSON.stringify(item.toolConfig,null,4): null,
                                            showEditConfig: true,
                                            modelIdOption: this.constructModelOption(item.modelId)
                                        })
                                        var configs = this.state.configs;
                                        const newConfigs = configs.filter(c => c.id !== item.id);
                                        this.setState({configs: newConfigs});
                                    }} /> &nbsp;
                                    <Button iconName="remove" onClick={()=> 
                                        {
                                            var configs = this.state.configs;
                                            const newConfigs = configs.filter(c => c.id !== item.id);
                                            this.setState({configs: newConfigs});
                                        }
                                    } />
                                    </div>
                                ),
                            }
                        ]}
                        items={this.state.configs}
                        loadingText="Loading prompts"
                        sortingDisabled
                    />
                    <br/>
                </div>
                }
                <ButtonDropdown
                    onItemClick={({ detail }) =>  {
                        this.setFramePrompt(detail.id);
                        this.setState({showEditConfig: true});
                    }}
                    items={this.state.sampleConfigs?.map(item => {
                        return {
                            text: item.name,
                            id: item.id,
                            itemType: "checkbox",
                            checked: item.id == this.state.selectedPromptId
                        };
                    })}>Add a new prompt
                </ButtonDropdown>
                <br/>
                {this.state.warnings.length > 0 && this.state.warnings.map(w=> {return <div className='warnings'>{w}</div>})}
                {this.state.showEditConfig &&
                <div className='prompt'>
                    <div className='label'>Display name</div>
                    <Input value={this.state.name} onChange={
                        ({detail})=>this.setState({name: detail.value})
                    }></Input>
                    <div className='label'>Select a model</div>
                    <Select selectedOption={this.state.modelIdOption}
                        onChange={({ detail }) => {this.setState({modelIdOption: detail.selectedOption})}}
                        options={this.state.models.map(item => {
                            return {
                                label: item.name,
                                value: item.value,
                            };
                        })} />
                    <div className='label'>Input a prompt</div>
                    <Textarea rows={4} value={this.state.prompt} onChange={
                        ({detail})=>{
                                this.setState({
                                    prompt: detail.value,
                                });
                        }                                                
                    }></Textarea>
                    <ExpandableSection headerText="Tool Configuration">
                        <Textarea rows={10} onChange={({ detail }) => this.setState({toolConfig: detail.value})} value={this.state.toolConfig}></Textarea>
                    </ExpandableSection>
                    <br/>
                    <ExpandableSection headerText="Inference Configuration">
                        <ColumnLayout columns={3}>
                            <Container>
                                <div className='label'>Maximum Output Tokens</div>
                                <Slider
                                    onChange={({ detail }) => this.setState({maxTokens: detail.value})}
                                    value={this.state.maxTokens}
                                    max={32000}
                                    min={0}
                                    step={1}
                                    />                            
                            </Container>
                            <Container>
                                <div className='label'>Top P</div>
                                <Slider
                                    onChange={({ detail }) => this.setState({topP: detail.value})}
                                    value={this.state.topP}
                                    max={1}
                                    min={0}
                                    step={0.1}
                                    />                            
                            </Container>
                            <Container>
                                <div className='label'>Temperature</div>
                                <Slider
                                    onChange={({ detail }) => this.setState({temperature: detail.value})}
                                    value={this.state.temperature}
                                    max={1}
                                    min={0}
                                    step={0.1}
                                    />                            
                            </Container>

                        </ColumnLayout>
                    </ExpandableSection>
                    <div className='action'>
                        <Button formAction="none" variant="link" onClick={()=> this.setState({
                            showEditConfig: false,
                            warnings: []
                        })}>Cancel</Button>
                        <Button variant="primary" onClick={()=>{
                            var {config, warnings} = this.constructConfig();
                                if (warnings.length === 0) {
                                    var configs = this.state.configs;
                                    configs.push(config);    
                                    this.setState({
                                        configs: configs,
                                        showEditConfig: false,
                                    }) ;
                                    this.setFramePrompt("default");
                                }
                            }
                        }>Save Configuration</Button>
                    </div>
                </div>}
            </div>
  };
};
export default VideoFramePromptConfig;