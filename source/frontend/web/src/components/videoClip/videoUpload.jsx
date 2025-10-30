import React, { Component, createRef } from 'react';
import './videoUpload.css'
import { FetchPost } from "../../resources/data-provider";
import { Textarea, Tabs, RadioGroup, Link, FileUpload, Select, ExpandableSection, FormField, Input, Wizard, Container, Header, SpaceBetween, Alert, Toggle, ProgressBar, ColumnLayout, Popover, StatusIndicator} from '@cloudscape-design/components';
import { getCurrentUser } from 'aws-amplify/auth';
import VideoSampleSetting from './videoSampleSetting'

class VideoUpload extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            status: null, // null, loading, loaded
            alert: null,
            uploadFiles: [],
            numChunks: null,
            uploadedChunks: 0,

            taskName: null,

            request: null,

            activeStepIndex: 0,
            fileUploadedCounter: false,
            currentUploadingFileName: null,
        };
        this.item = null;
        this.llmParameters = null;

        this.frameSampleSettingRef = createRef();
        this.mmEmbedSettingRef = createRef();

    }

    resetState = () => {
        this.setState({
            status: null, // null, loading, loaded
            alert: null,
            uploadFiles: [],
            numChunks: null,
            uploadedChunks: 0,
            taskName: null,
            request: null,
            activeStepIndex: 0,
            fileUploadedCounter: false,
            currentUploadingFileName: null
        });
        this.uploadTimer = null;
    }

    handleNavigate = e => {
        if(e.detail.requestedStepIndex === 1) {
            if (this.state.uploadFiles.length === 0) {
                this.setState({alert: 'Please select a video file to continue.'});
                return;
            }
        }
        else if(e.detail.requestedStepIndex === 2) {

            const taskReq = this.frameSampleSettingRef.current.getRequest();
            if (taskReq === null) return;
            this.setState({alert: null, request: taskReq})

        }
        this.setState({aler: null, activeStepIndex: e.detail.requestedStepIndex})
    }

    async handleSumbitTask () {
        for (let i = 0; i < this.state.uploadFiles.length; i++) {
            this.generatePresignedUrls(this.state.uploadFiles[i]);
        }
    }

    generatePresignedUrls (file) {
        // Wait if other file is uploading
        if (this.state.currentUploadingFileName !== null)
            setTimeout(() => {
                console.log(`Waiting`);
            }, 1000); 

        this.setState({currentUploadingFileName: file.name})
        //console.log(fileName);
        const fileSize = file.size;
        const numChunks = Math.ceil(fileSize / (5 * 1024 * 1024));
        this.setState({numChunks: numChunks});  

        this.setState({status: "generateurl"});
        FetchPost("/extraction/video/manage-s3-presigned-url", {"FileName": file.name, "NumParts": numChunks, "Action": "create"}, "ExtrService")
            .then((data) => {
                  //console.log(resp);
                  if (data.statusCode !== 200) {
                      this.setState( {status: null, alert: data.body});
                  }
                  else {
                      if (data.body !== null) {
                          return this.uploadFile({
                            taskId: data.body.TaskId,
                            uploadS3Url: data.body.UploadUrl,
                            uploadedS3Bucket: data.body.S3Bucket,
                            uploadedS3KeyVideo: data.body.S3Key,
                            status: null,
                            alert: null,
                            uploadId: data.body.UploadId,
                            uploadPartUrls: data.body.UploadPartUrls,
                            numChunks: numChunks
                        })
                      }
                  }
              })
              .catch((err) => {
                  this.setState( {status: null, alert: err.message});
              });  
    }

    async submitTask (urlResp) {
        //console.log(urlResp);
        var payload = this.state.request;
        payload.TaskId = urlResp.taskId;
        payload.FileName = this.state.uploadFiles[0].name;
        payload.TaskName = this.state.taskName;
        payload.TaskType = "clip";
        payload.Video = {
              "S3Object": {
                "Bucket": urlResp.uploadedS3Bucket,
                "Key": urlResp.uploadedS3KeyVideo,
              },
            };
        //console.log(payload)

        this.setState({status: "loading"});
        const { username } = getCurrentUser().then((username) => {
            payload["RequestBy"] = username.username;
            // Start task
            FetchPost('/extraction/video/start-task', payload, "ExtrService")
                .then((data) => {
                    this.setState({currentUploadingFileName: null})
                    var resp = data.body;
                    if (data.statusCode !== 200) {
                        //console.log(data.body);
                        // Handle error response - check if it's an object with error property
                        const errorMessage = typeof data.body === 'object' && data.body.error 
                            ? data.body.error 
                            : data.body;
                        this.setState( {status: null, alert: errorMessage});
                    }
                    else {
                        if (this.state.fileUploadedCounter == this.state.uploadFiles.length) {
                            this.resetState(null);
                            this.props.onSubmit();
                        }
                    }
                })
                .catch((err) => {
                    this.setState({currentUploadingFileName: null})
                    //console.log(err.message);
                    this.setState( {status: null, alert: err.message});
                });                      
            }
        )

    }

    async uploadFile(urlResp) {
        this.setState({status: "uploading"});
        let file = this.state.uploadFiles[0];
        if (urlResp.uploadPartUrls === null || urlResp.uploadPartUrls.length === 0) return;
            //console.log(this.state);
            // Upload each part to the corresponding pre-signed URL
            const uploadPromises = [];
            let parts = [];
            for (let i = 0; i < urlResp.numChunks; i++) {
              const startByte = i * (5 * 1024 * 1024);
              const endByte = Math.min(startByte + (5 * 1024 * 1024), file.size);
              const chunk = file.slice(startByte, endByte);
        
              const formData = new FormData();
              formData.append('file', chunk);
        
              let retries = 0;
              const uploadPromise = await fetch(urlResp.uploadPartUrls[i], {
                method: 'PUT',
                headers: {'Content-Type': ''},
                body: chunk,
              }).then((response) => {
                if (response.ok) {
                    //console.log(response.headers.get('Etag'));
                    parts.push({'ETag': response.headers.get('Etag'), 'PartNumber': i + 1})
                    this.setState({uploadedChunks: this.state.uploadedChunks + 1})
                    //console.log("uploaded", i, parts);
                    //console.log(this.state);
                }
              });
              uploadPromises.push(uploadPromise);
            };

            await Promise.all(uploadPromises).then(() => {
                    this.setState({fileUploadedCounter: this.state.fileUploadedCounter + 1});
                    //console.log("all completed");
                }
            ).then((response) => {
                // Call complete endpoint
                let payload = {
                    "TaskId": urlResp.taskId,
                    "FileName": file.name, 
                    "MultipartUpload": parts, 
                    "UploadId": urlResp.uploadId, 
                    "Action": "complete"
                };
                FetchPost("/extraction/video/manage-s3-presigned-url", payload, "ExtrService")
                .then((result) => {
                    if (result.statusCode !== 200) {
                        this.setState( {alert: result.body});
                    }
                    else {
                        this.setState( {alert: null});
                        this.submitTask(urlResp);
                    }   
                })
                .catch((err) => {
                    this.setState( {alert: err.message});
                })
            });
    }

    handelFileChange = (e) => {
        const supportedFormats = ['avi', 'mov', 'mp4'];
        const filteredFiles = [];
        const invalidFiles= [];

        for (let i = 0; i < e.detail.value.length; i++) {
            const fileName = e.detail.value[i].name;
            const fileExtension = fileName.split('.').pop().toLowerCase();
    
            if (supportedFormats.includes(fileExtension)) {
                filteredFiles.push(e.detail.value[i]);
            } else {
                invalidFiles.push(fileName);
            }
        }
        this.setState({
            uploadFiles: filteredFiles,
            alert: invalidFiles.length === 0?null: `File(s) "${invalidFiles.join(', ')}" not in supported format (avi, mov, mp4) and has been removed.`
        });

        if (this.state.taskName === null || this.state.taskName.length === 0) {
          this.setState({taskName: e.detail.value[0].name})
        }
    }

    render() {
        return (
            <div className="videoupload">
                {this.state.alert !== null?
                <div><Alert statusIconAriaLabel="Warning" type="warning">{this.state.alert}</Alert><br/></div>
                :<div/>}
                <Wizard
                    i18nStrings={{
                        stepNumberLabel: stepNumber =>
                        `Step ${stepNumber}`,
                        collapsedStepsLabel: (stepNumber, stepsCount) =>
                        `Step ${stepNumber} of ${stepsCount}`,
                        skipToButtonLabel: (step, stepNumber) =>
                        `Skip to ${step.title}`,
                        navigationAriaLabel: "Steps",
                        cancelButton: "Cancel",
                        previousButton: "Previous",
                        nextButton: "Next",
                        submitButton: "Upload video and start analysis",
                        optional: "optional"
                    }}
                    onNavigate={this.handleNavigate}
                    onCancel={()=>{this.resetState();this.props.onCancel(null);}}
                    onSubmit={()=>this.handleSumbitTask()}
                    isLoadingNextStep={this.state.status !== null}
                    activeStepIndex={this.state.activeStepIndex}
                    steps={[
                        {
                            title: "Select a video",
                            description:
                                "Upload a video file from your local disk. Supported format: .mp4, .mov, .avi",
                            content: (
                                <Container
                                    header={
                                        <Header variant="h2">
                                        Upload a video file
                                        </Header>
                                    }
                                >
                                  <FormField stretch label="Task Name" >
                                      <Input value={this.state.taskName} onChange={({ detail }) => this.setState({taskName: detail.value})}></Input>
                                  </FormField>
                                  <br/>
                                <FileUpload
                                    onChange={this.handelFileChange}
                                    value={this.state.uploadFiles}
                                    i18nStrings={{
                                    uploadButtonText: e =>
                                        e ? "Choose files" : "Choose file",
                                    dropzoneText: e =>
                                        e
                                        ? "Drop files to upload"
                                        : "Drop file to upload",
                                    removeFileAriaLabel: e =>
                                        `Remove file ${e + 1}`,
                                    limitShowFewer: "Show fewer files",
                                    limitShowMore: "Show more files",
                                    errorIconAriaLabel: "Error"
                                    }}
                                    showFileLastModified
                                    showFileSize
                                    showFileThumbnail
                                    tokenLimit={3}
                                    multiple={false}
                                    constraintText="Supported video format: .mp4, .mov, .avi"
                                />
                                </Container>                                
                            )
                        },
                        {
                        title: "Extraction settings",
                        content: (
                            <SpaceBetween direction="vertical" size="l">
                              <VideoSampleSetting ref={this.frameSampleSettingRef} />
                            </SpaceBetween>
                        ),
                        },
                        {
                            title: "Upload vidoe and start analysis",
                            info: <Link variant="info">Info</Link>,
                            description:
                                "Confirm the videos below and start analysis",
                            content: (
                                <Container
                                    header={
                                        <Header variant="h2">
                                        Upload a video file
                                        </Header>
                                    }
                                >
                                    {this.state.uploadFiles.map((file,i)=>{
                                        return <div key={file + i.toString()} className='uploadedfile'>
                                            <div className='filename'>{file.name}</div>
                                            <div className='attribute'>{(file.size / (1024 * 1024)).toFixed(2)} MB</div>
                                            {this.state.currentUploadingFileName === file.name &&
                                                <div>
                                                    <ProgressBar
                                                        value={this.state.numChunks && this.state.uploadedChunks?(this.state.uploadedChunks/this.state.numChunks)*100:0}
                                                        status={this.state.numChunks && this.state.uploadedChunks && this.state.uploadedChunks === this.state.numChunks? "success":"in-progress"}
                                                        label="Uploading file"
                                                    />
                                                    <br/>
                                                </div>
                                            }                                        
                                        </div>
                                    })}

                                    
                                </Container>
                            )
                        },
                    ]}
                />

            </div>
        );
    }
}

export default VideoUpload;